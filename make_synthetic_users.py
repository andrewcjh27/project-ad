"""
Project AD — Synthetic Audience Generator (SQLite) + Persona Synthesis
======================================================================
Creates a realistic, queryable synthetic audience for the Starbucks demo,
GROUPS it into ad-preference cohorts across MANY personality dimensions, and
fuses each cohort's trait-mixture into ONE personalized persona — the input
that lets the generation pipeline speak to a blended persona instead of a
single bucket.

WHY THIS SHAPE: ad personalization here is per-SEGMENT, not per-user (see
Audience-Segmentation-and-Scaling.md). But a segment is not "a or b" — it's a
mixture of interests, lifecycle/value, behavior, and demographics. So we:
  1) generate users with the signals that drive grouping,
  2) cluster them on the FULL trait vector (interest + lifecycle/value +
     behavior + demographics) so cohorts are diverse mixtures, and
  3) synthesize each cohort's mixture into one named persona (LLM when a key is
     present, deterministic blend otherwise).

STAND-IN: users are sampled from interest ARCHETYPES (so natural structure
exists); grouping uses TF-IDF + one-hot/standardized features as the offline
embedding stand-in; the persona narrative falls back to a deterministic
composer when no LLM key is set. Deterministic (seeded) and reproducible.

Run:
    python3 make_synthetic_users.py            # -> audience.db (default 500 users)
    python3 make_synthetic_users.py 2000

Tables:
    users          one row per synthetic user (the grouping INPUT)
    segments       one row per cohort, incl. the synthesized persona (OUTPUT)
    user_segments  user -> segment membership
"""
import sys
import json
import sqlite3
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, normalize
from sklearn.cluster import KMeans

import llm_agent   # optional LLM persona narrative (falls back to deterministic)

RNG = np.random.default_rng(42)
DB_PATH = "audience.db"

# ---------------------------------------------------------------------------
# Interest archetypes -> drive natural structure. Terms + the brand attributes
# they imply (kept consistent with product_catalog.json categories/seasons).
# ---------------------------------------------------------------------------
ARCHETYPES = {
    "fall_seasonal":   {"terms": "pumpkin spice fall autumn seasonal cozy warm latte cinnamon morning ritual",
                        "season": "fall", "temp": "hot", "category": "seasonal_bev"},
    "cold_brew_reg":   {"terms": "cold brew iced refreshing afternoon bold smooth everyday nitro",
                        "season": "all", "temp": "cold", "category": "cold_coffee"},
    "tea_wellness":    {"terms": "matcha green tea wellness healthy calm earthy chai cozy",
                        "season": "all", "temp": "hot", "category": "tea"},
    "holiday_festive": {"terms": "peppermint mocha holiday festive winter caramel cozy seasonal chocolate",
                        "season": "holiday", "temp": "hot", "category": "seasonal_bev"},
    "summer_fruity":   {"terms": "refresher strawberry fruity summer bright light energizing iced",
                        "season": "summer", "temp": "cold", "category": "refresher"},
    "commuter_food":   {"terms": "breakfast sandwich croissant morning food coffee latte quick everyday filling",
                        "season": "all", "temp": "hot", "category": "food"},
    "classic_simple":  {"terms": "pike place brewed black coffee classic simple everyday morning",
                        "season": "all", "temp": "hot", "category": "core_bev"},
}
ARCH_NAMES = list(ARCHETYPES.keys())
ARCH_LABEL = {
    "fall_seasonal": "seasonal sipper", "cold_brew_reg": "cold-brew regular",
    "tea_wellness": "tea & wellness seeker", "holiday_festive": "holiday treater",
    "summer_fruity": "refresher fan", "commuter_food": "grab-and-go commuter",
    "classic_simple": "classic purist",
}

LIFECYCLES = ["new", "loyal", "lapsed", "vip"]
LIFE_P     = [0.20, 0.45, 0.25, 0.10]
DAYPARTS   = ["morning", "afternoon", "evening"]
AGE_BANDS  = ["18-24", "25-34", "35-44", "45-54", "55+"]
REGIONS    = ["US-West", "US-Midwest", "US-South", "US-Northeast"]
CHANNELS   = ["app", "in_store", "web"]
DEVICES    = ["ios", "android", "desktop"]

LIFE_BEHAVIOR = {
    "new":    {"visits": (1, 4),  "recency": (0, 21),   "loyalty_p": 0.4, "spend_mult": 0.9},
    "loyal":  {"visits": (8, 20), "recency": (0, 7),    "loyalty_p": 0.9, "spend_mult": 1.0},
    "lapsed": {"visits": (0, 2),  "recency": (45, 180), "loyalty_p": 0.6, "spend_mult": 0.8},
    "vip":    {"visits": (16, 30),"recency": (0, 4),    "loyalty_p": 0.98,"spend_mult": 1.4},
}
PRICE_SPEND = {"low": (4.0, 7.0), "mid": (7.0, 12.0), "high": (12.0, 22.0)}

# Trait axes blended into the persona + used as clustering features.
CAT_FIELDS = ["lifecycle", "daypart", "season_affinity", "temp_pref", "fav_category",
              "price_band", "age_band", "region", "channel", "device"]
NUM_FIELDS = ["visits_per_month", "avg_spend", "days_since_last_visit",
              "loyalty_member", "marketing_opt_in"]


def make_users(n=500):
    """Sample `n` users from interest archetypes with realistic, grouping-relevant fields."""
    users = []
    for i in range(n):
        arch = ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]
        meta = ARCHETYPES[arch]
        base = meta["terms"].split()
        k = int(RNG.integers(5, len(base) + 1))
        terms = list(RNG.choice(base, size=k, replace=False))
        if RNG.random() < 0.25:                                  # secondary interest (messiness)
            other = ARCHETYPES[ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]]["terms"].split()
            terms += list(RNG.choice(other, size=2, replace=False))

        life = str(RNG.choice(LIFECYCLES, p=LIFE_P))
        beh = LIFE_BEHAVIOR[life]
        price_band = str(RNG.choice(["low", "mid", "high"], p=[0.3, 0.5, 0.2]))
        lo, hi = PRICE_SPEND[price_band]

        users.append({
            "user_id": f"u{i:05d}",
            "archetype": arch,                                   # ground truth (validation only)
            "interest_text": " ".join(terms),
            "lifecycle": life,
            "daypart": str(RNG.choice(DAYPARTS, p=[0.5, 0.35, 0.15])),
            "season_affinity": meta["season"],
            "temp_pref": meta["temp"],
            "fav_category": meta["category"],
            "price_band": price_band,
            "age_band": str(RNG.choice(AGE_BANDS, p=[0.22, 0.30, 0.22, 0.16, 0.10])),
            "region": str(RNG.choice(REGIONS)),
            "channel": str(RNG.choice(CHANNELS, p=[0.5, 0.35, 0.15])),
            "device": str(RNG.choice(DEVICES, p=[0.45, 0.4, 0.15])),
            "visits_per_month": int(RNG.integers(beh["visits"][0], beh["visits"][1] + 1)),
            "avg_spend": round(float(RNG.uniform(lo, hi)) * beh["spend_mult"], 2),
            "days_since_last_visit": int(RNG.integers(beh["recency"][0], beh["recency"][1] + 1)),
            "loyalty_member": int(RNG.random() < beh["loyalty_p"]),
            "marketing_opt_in": int(RNG.random() < 0.72),        # consent: only target opted-in
        })
    return users


# ---------------------------------------------------------------------------
# Grouping: cluster on the FULL trait vector so cohorts are diverse mixtures.
# ---------------------------------------------------------------------------
def _feature_matrix(users):
    """Blend interest text + one-hot categoricals + standardized numerics into one space."""
    tfidf = TfidfVectorizer(min_df=1, stop_words="english")
    Xi = normalize(tfidf.fit_transform([u["interest_text"] for u in users]).toarray())
    feature_names = np.array(tfidf.get_feature_names_out())
    Xc = normalize(OneHotEncoder(sparse_output=False).fit_transform(
        [[u[f] for f in CAT_FIELDS] for u in users]))
    Xn = StandardScaler().fit_transform(
        np.array([[float(u[f]) for f in NUM_FIELDS] for u in users], dtype=float))
    X = np.hstack([1.0 * Xi, 0.6 * Xc, 0.4 * Xn])   # weight interest > behavior > raw numerics
    return X, Xi, feature_names


def _mix(values, top=3):
    """Top categories of a trait with their proportions (the 'mixture')."""
    c = Counter(values)
    total = sum(c.values())
    return [[k, round(v / total, 2)] for k, v in c.most_common(top)]


def build_persona(members, users, Xi, feature_names):
    """Fuse a cohort's members into a STRUCTURED trait-mixture persona."""
    centroid = Xi[members].mean(axis=0)
    top_terms = [t for t in feature_names[np.argsort(centroid)[::-1][:6]]]

    def vals(f):
        return [users[m][f] for m in members]

    return {
        "size": int(len(members)),
        "interest_terms": top_terms,
        "archetype_mix": _mix(vals("archetype")),
        "lifecycle_mix": _mix(vals("lifecycle")),
        "season_mix": _mix(vals("season_affinity")),
        "temp_mix": _mix(vals("temp_pref")),
        "category_mix": _mix(vals("fav_category")),
        "daypart_mix": _mix(vals("daypart")),
        "price_mix": _mix(vals("price_band")),
        "age_mix": _mix(vals("age_band")),
        "region_mix": _mix(vals("region")),
        "channel_mix": _mix(vals("channel")),
        "device_mix": _mix(vals("device")),
        "value": {
            "avg_visits": round(float(np.mean(vals("visits_per_month"))), 1),
            "avg_spend": round(float(np.mean(vals("avg_spend"))), 2),
            "avg_recency_days": round(float(np.mean(vals("days_since_last_visit"))), 1),
            "loyalty_rate": round(float(np.mean(vals("loyalty_member"))), 2),
            "opt_in_rate": round(float(np.mean(vals("marketing_opt_in"))), 2),
        },
    }


LIFE_LABEL = {"loyal": "Loyal", "new": "New", "lapsed": "Lapsed", "vip": "VIP"}


def deterministic_persona_copy(p):
    """Compose a named persona + narrative + angle from the mixture (offline fallback)."""
    prim = p["archetype_mix"][0]
    sec = p["archetype_mix"][1] if len(p["archetype_mix"]) > 1 else None
    life = p["lifecycle_mix"][0][0]
    daypart = p["daypart_mix"][0][0]
    price = p["price_mix"][0][0]
    age = p["age_mix"][0][0]
    channel = p["channel_mix"][0][0]
    prim_label = ARCH_LABEL.get(prim[0], prim[0])
    qualifier = "Premium " if p["value"]["avg_spend"] >= 14 else ""
    name = f"The {qualifier}{LIFE_LABEL.get(life, life.title())} {prim_label.title()}"
    sec_txt = (f" with a {ARCH_LABEL.get(sec[0], sec[0])} streak"
               if sec and sec[1] >= 0.15 else "")
    summary = (f"A {life}-leaning {daypart} cohort centered on the {prim_label} "
               f"({int(prim[1]*100)}%){sec_txt}; {price}-price (~${p['value']['avg_spend']}/visit), "
               f"skews {age}, {channel}-first.")
    angle = (f"minimal and understated; speak to a {life} {prim_label}, calm and personal — "
             f"acknowledge the {daypart} ritual without a hard sell")
    return name, summary, angle


def personalize(persona):
    """LLM persona narrative when a key is present, else deterministic blend."""
    res = llm_agent.generate_persona(persona)
    if res:
        return res
    name, summary, angle = deterministic_persona_copy(persona)
    return name, summary, angle, "rule-based(from mix)"


def group_into_segments(users, n_segments=None):
    """Cluster users on the full trait vector -> diverse cohorts, each with a persona."""
    X, Xi, feature_names = _feature_matrix(users)
    n = len(users)
    k = n_segments or max(6, min(15, n // 40))
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X).labels_

    segments, membership = [], []
    for c in range(k):
        members = np.where(labels == c)[0]
        if len(members) == 0:
            continue
        sid = f"seg_{c:02d}"
        persona = build_persona(members, users, Xi, feature_names)
        name, summary, angle, src = personalize(persona)
        dom_arch, dom_share = persona["archetype_mix"][0]
        segments.append({
            "segment_id": sid,
            "size": int(len(members)),
            "lifecycle": persona["lifecycle_mix"][0][0],          # lean (top lifecycle)
            "dominant_interest": " ".join(persona["interest_terms"]),
            "dominant_archetype": dom_arch,
            "purity": dom_share,                                  # dominant-archetype share
            "top_daypart": persona["daypart_mix"][0][0],
            "top_season": persona["season_mix"][0][0],
            "persona_name": name,
            "persona_summary": summary,
            "persona_angle": angle,
            "persona_source": src,
            "persona_json": json.dumps(persona),
        })
        membership += [(users[m]["user_id"], sid) for m in members]
    return segments, membership


def write_db(users, segments, membership, path=DB_PATH):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS segments;
        DROP TABLE IF EXISTS user_segments;
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            archetype TEXT, interest_text TEXT, lifecycle TEXT, daypart TEXT,
            season_affinity TEXT, temp_pref TEXT, fav_category TEXT, price_band TEXT,
            age_band TEXT, region TEXT, channel TEXT, device TEXT,
            visits_per_month INTEGER, avg_spend REAL, days_since_last_visit INTEGER,
            loyalty_member INTEGER, marketing_opt_in INTEGER
        );
        CREATE TABLE segments (
            segment_id TEXT PRIMARY KEY, size INTEGER, lifecycle TEXT,
            dominant_interest TEXT, dominant_archetype TEXT, purity REAL,
            top_daypart TEXT, top_season TEXT,
            persona_name TEXT, persona_summary TEXT, persona_angle TEXT,
            persona_source TEXT, persona_json TEXT
        );
        CREATE TABLE user_segments (
            user_id TEXT, segment_id TEXT,
            PRIMARY KEY (user_id, segment_id)
        );
    """)
    ucols = ["user_id", "archetype", "interest_text", "lifecycle", "daypart",
             "season_affinity", "temp_pref", "fav_category", "price_band", "age_band",
             "region", "channel", "device", "visits_per_month", "avg_spend",
             "days_since_last_visit", "loyalty_member", "marketing_opt_in"]
    cur.executemany(f"INSERT INTO users ({','.join(ucols)}) VALUES ({','.join('?'*len(ucols))})",
                    [[u[c] for c in ucols] for u in users])
    scols = ["segment_id", "size", "lifecycle", "dominant_interest", "dominant_archetype",
             "purity", "top_daypart", "top_season", "persona_name", "persona_summary",
             "persona_angle", "persona_source", "persona_json"]
    cur.executemany(f"INSERT INTO segments ({','.join(scols)}) VALUES ({','.join('?'*len(scols))})",
                    [[s[c] for c in scols] for s in segments])
    cur.executemany("INSERT INTO user_segments (user_id, segment_id) VALUES (?, ?)", membership)
    con.commit()
    con.close()


def segment_for_pipeline(segment_id, path=DB_PATH):
    """Load a segment (with its persona) in the shape Orchestrator.run expects."""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    s = con.execute("SELECT * FROM segments WHERE segment_id=?", (segment_id,)).fetchone()
    con.close()
    if s is None:
        raise KeyError(f"no segment {segment_id!r} in {path}")
    top_interest = s["dominant_interest"].split()[0] if s["dominant_interest"] else "coffee"
    return {
        "segment_id": s["segment_id"], "size": s["size"], "lifecycle": s["lifecycle"],
        "dominant_interest": s["dominant_interest"], "daypart": s["top_daypart"],
        "season": s["top_season"],
        "signals": [f"interest:{top_interest}", f"behavioral:{s['top_daypart']}",
                    f"lifecycle:{s['lifecycle']}"],
        "persona": {
            "name": s["persona_name"], "summary": s["persona_summary"],
            "angle": s["persona_angle"], "source": s["persona_source"],
            "mix": json.loads(s["persona_json"]),
        },
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    users = make_users(n)
    segments, membership = group_into_segments(users)
    write_db(users, segments, membership)

    src = segments[0]["persona_source"] if segments else "n/a"
    print(f"Wrote {DB_PATH}: {len(users)} users -> {len(segments)} cohorts "
          f"(personas via {src})")
    print(f"{'segment':9s} {'size':>4s}  {'persona':28s}  summary")
    print("-" * 110)
    for s in sorted(segments, key=lambda s: -s["size"]):
        print(f"{s['segment_id']:9s} {s['size']:4d}  {s['persona_name'][:28]:28s}  {s['persona_summary']}")
    print("\nFeed any cohort straight into the pipeline, e.g.:")
    print("  from make_synthetic_users import segment_for_pipeline")
    print("  Orchestrator().run_campaign(segment_for_pipeline('seg_00'), 'campaign_x')")
