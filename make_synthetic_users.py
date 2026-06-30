"""
Project AD — Synthetic Audience Generator (SQLite)
==================================================
Creates a realistic, queryable synthetic audience for the Starbucks demo and
GROUPS it into ad-preference segments — the missing input that lets the
generation pipeline run per real cohort instead of one hardcoded segment.

WHY THIS SHAPE: ad personalization here is per-SEGMENT, not per-user (see
Audience-Segmentation-and-Scaling.md). So we generate users with the signals
that actually drive grouping (interest, lifecycle, behavior, value), then
facet + cluster them into segments — the same mechanics validated in
`Starbucks/spike_segmentation_matching.py`, just persisted to SQLite.

STAND-IN: users are sampled from interest ARCHETYPES (so natural clusters
exist) and the grouping uses TF-IDF over interest text as the offline embedding
stand-in (swap `product_discovery._embed` for a hosted model later — same
mechanics). Deterministic (seeded) so the dataset is reproducible.

Run:
    python3 make_synthetic_users.py            # -> audience.db (default 500 users)
    python3 make_synthetic_users.py 2000       # -> 2000 users

Tables:
    users          one row per synthetic user (the grouping INPUT)
    segments       one row per ad-preference cohort (the grouping OUTPUT)
    user_segments  user -> segment membership

A segment row is shaped to feed Orchestrator.run / run_campaign directly
(see `segment_for_pipeline`).
"""
import sys
import json
import sqlite3
from collections import Counter, defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

RNG = np.random.default_rng(42)
DB_PATH = "audience.db"

# ---------------------------------------------------------------------------
# Interest archetypes -> drive natural clusters. Terms + the brand attributes
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

LIFECYCLES = ["new", "loyal", "lapsed", "vip"]
LIFE_P     = [0.20, 0.45, 0.25, 0.10]
DAYPARTS   = ["morning", "afternoon", "evening"]
AGE_BANDS  = ["18-24", "25-34", "35-44", "45-54", "55+"]
REGIONS    = ["US-West", "US-Midwest", "US-South", "US-Northeast"]
CHANNELS   = ["app", "in_store", "web"]
DEVICES    = ["ios", "android", "desktop"]

# Behavior priors keyed by lifecycle (visits/mo, days-since-last, loyalty odds)
LIFE_BEHAVIOR = {
    "new":    {"visits": (1, 4),  "recency": (0, 21),   "loyalty_p": 0.4, "spend_mult": 0.9},
    "loyal":  {"visits": (8, 20), "recency": (0, 7),    "loyalty_p": 0.9, "spend_mult": 1.0},
    "lapsed": {"visits": (0, 2),  "recency": (45, 180), "loyalty_p": 0.6, "spend_mult": 0.8},
    "vip":    {"visits": (16, 30),"recency": (0, 4),    "loyalty_p": 0.98,"spend_mult": 1.4},
}
PRICE_SPEND = {"low": (4.0, 7.0), "mid": (7.0, 12.0), "high": (12.0, 22.0)}


def make_users(n=500):
    """Sample `n` users from interest archetypes with realistic, grouping-relevant fields."""
    users = []
    for i in range(n):
        arch = ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]
        meta = ARCHETYPES[arch]
        base = meta["terms"].split()
        # Noisy subset of the archetype's interest terms (+ occasional secondary interest).
        k = int(RNG.integers(5, len(base) + 1))
        terms = list(RNG.choice(base, size=k, replace=False))
        if RNG.random() < 0.25:
            other = ARCHETYPES[ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]]["terms"].split()
            terms += list(RNG.choice(other, size=2, replace=False))

        life = str(RNG.choice(LIFECYCLES, p=LIFE_P))
        beh = LIFE_BEHAVIOR[life]
        price_band = str(RNG.choice(["low", "mid", "high"], p=[0.3, 0.5, 0.2]))
        lo, hi = PRICE_SPEND[price_band]

        users.append({
            "user_id": f"u{i:05d}",
            "archetype": arch,                                   # ground truth (validation only)
            "interest_text": " ".join(terms),                    # drives embedding/grouping
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


def group_into_segments(users, min_seg=12, max_k=4):
    """Facet by lifecycle, then KMeans on interest vectors -> ad-preference cohorts.

    Mirrors Starbucks/spike_segmentation_matching.py. Returns (segments, membership)
    where each segment carries a `dominant_interest` ready for product retrieval.
    """
    texts = [u["interest_text"] for u in users]
    vec = TfidfVectorizer(min_df=1, stop_words="english")
    X = vec.fit_transform(texts).toarray()
    feature_names = np.array(vec.get_feature_names_out())

    by_life = defaultdict(list)
    for idx, u in enumerate(users):
        by_life[u["lifecycle"]].append(idx)

    segments, membership = [], []
    for life, idxs in by_life.items():
        idxs = np.array(idxs)
        if len(idxs) < min_seg:
            clusters = {0: idxs}
        else:
            k = max(1, min(max_k, len(idxs) // min_seg))
            labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X[idxs]).labels_
            clusters = {c: idxs[labels == c] for c in range(k) if (labels == c).any()}

        for c, members in clusters.items():
            centroid = X[members].mean(axis=0)
            top_terms = [t for t in feature_names[np.argsort(centroid)[::-1][:6]]]
            archs = Counter(users[m]["archetype"] for m in members)
            dom_arch, dom_n = archs.most_common(1)[0]
            dayparts = Counter(users[m]["daypart"] for m in members)
            seasons = Counter(users[m]["season_affinity"] for m in members)
            sid = f"seg_{life}_{c}"
            segments.append({
                "segment_id": sid,
                "lifecycle": life,
                "size": int(len(members)),
                "dominant_interest": " ".join(top_terms),
                "dominant_archetype": dom_arch,
                "purity": round(dom_n / len(members), 3),
                "top_daypart": dayparts.most_common(1)[0][0],
                "top_season": seasons.most_common(1)[0][0],
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
            segment_id TEXT PRIMARY KEY, lifecycle TEXT, size INTEGER,
            dominant_interest TEXT, dominant_archetype TEXT, purity REAL,
            top_daypart TEXT, top_season TEXT
        );
        CREATE TABLE user_segments (
            user_id TEXT, segment_id TEXT,
            PRIMARY KEY (user_id, segment_id)
        );
    """)
    cols = ["user_id", "archetype", "interest_text", "lifecycle", "daypart",
            "season_affinity", "temp_pref", "fav_category", "price_band", "age_band",
            "region", "channel", "device", "visits_per_month", "avg_spend",
            "days_since_last_visit", "loyalty_member", "marketing_opt_in"]
    cur.executemany(f"INSERT INTO users ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                    [[u[c] for c in cols] for u in users])
    scols = ["segment_id", "lifecycle", "size", "dominant_interest", "dominant_archetype",
             "purity", "top_daypart", "top_season"]
    cur.executemany(f"INSERT INTO segments ({','.join(scols)}) VALUES ({','.join('?'*len(scols))})",
                    [[s[c] for c in scols] for s in segments])
    cur.executemany("INSERT INTO user_segments (user_id, segment_id) VALUES (?, ?)", membership)
    con.commit()
    con.close()


def segment_for_pipeline(segment_id, path=DB_PATH):
    """Load a segment as the dict shape Orchestrator.run / run_campaign expects."""
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
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    users = make_users(n)
    segments, membership = group_into_segments(users)
    write_db(users, segments, membership)

    purity = np.mean([s["purity"] for s in segments])
    print(f"Wrote {DB_PATH}: {len(users)} users -> {len(segments)} ad-preference segments "
          f"(mean purity {purity:.0%})")
    print(f"{'segment':14s} {'life':7s} {'size':>4s}  {'arch':16s}  dominant_interest")
    print("-" * 92)
    for s in sorted(segments, key=lambda s: (-s["size"]))[:12]:
        print(f"{s['segment_id']:14s} {s['lifecycle']:7s} {s['size']:4d}  "
              f"{s['dominant_archetype']:16s}  {s['dominant_interest']}")
    print("\nFeed any segment straight into the pipeline, e.g.:")
    print("  from make_synthetic_users import segment_for_pipeline")
    print("  Orchestrator().run_campaign(segment_for_pipeline('seg_loyal_0'), 'campaign_x')")
