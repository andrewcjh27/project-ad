"""
Project AD — Segmentation + Product-Matching Spike
==================================================
Validates the core pipeline BEFORE building generation:
  synthetic users -> facet+cluster into segments -> embed catalog
  -> hybrid retrieve+rank per segment -> top-K products.

Embeddings here use TF-IDF as a stand-in for a real embedding model so the
spike runs offline and deterministically. Production swaps in a hosted
embedding model (see Product-Matching-and-Recommendation.md §9); the pipeline
mechanics (facet -> cluster -> centroid -> retrieve -> rank) are identical.
"""

import numpy as np
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

RNG = np.random.default_rng(42)

# ----------------------------------------------------------------------------
# 1. Starbucks catalog (structured fields + semantic description)
# ----------------------------------------------------------------------------
CATALOG = [
    # id, category, season, temp, price, margin, description
    ("psl",            "seasonal_bev", "fall",    "hot",  5.95, "high", "Pumpkin Spice Latte espresso pumpkin cinnamon nutmeg autumn cozy nostalgic seasonal ritual warm"),
    ("pumpkin_ccb",    "seasonal_bev", "fall",    "cold", 5.75, "high", "Pumpkin Cream Cold Brew smooth cold brew pumpkin cream fall autumn refreshing seasonal"),
    ("peppermint_mocha","seasonal_bev","holiday", "hot",  5.95, "high", "Peppermint Mocha chocolate peppermint holiday festive winter cozy seasonal espresso"),
    ("caramel_brulee", "seasonal_bev", "holiday", "hot",  6.10, "high", "Caramel Brulee Latte caramel holiday festive winter rich sweet seasonal espresso"),
    ("latte",          "core_bev",     "all",     "hot",  4.95, "mid",  "Caffe Latte espresso steamed milk classic everyday smooth morning ritual"),
    ("cappuccino",     "core_bev",     "all",     "hot",  4.75, "mid",  "Cappuccino espresso foam classic morning everyday smooth"),
    ("caramel_macch",  "core_bev",     "all",     "hot",  5.45, "mid",  "Caramel Macchiato espresso vanilla caramel everyday sweet smooth morning"),
    ("pike_brewed",    "core_bev",     "all",     "hot",  3.25, "low",  "Pike Place brewed coffee classic simple everyday black morning ritual"),
    ("cold_brew",      "cold_coffee",  "all",     "cold", 4.95, "mid",  "Cold Brew smooth slow steeped bold refreshing afternoon iced everyday"),
    ("nitro",          "cold_coffee",  "all",     "cold", 5.25, "mid",  "Nitro Cold Brew creamy cascading smooth bold iced refreshing afternoon"),
    ("bss_espresso",   "cold_coffee",  "all",     "cold", 5.75, "high", "Iced Brown Sugar Oatmilk Shaken Espresso oatmilk brown sugar shaken iced trendy refreshing"),
    ("matcha_latte",   "tea",          "all",     "hot",  5.25, "mid",  "Matcha Green Tea Latte matcha green tea healthy wellness smooth earthy calm"),
    ("chai_latte",     "tea",          "all",     "hot",  5.25, "mid",  "Chai Tea Latte spiced chai cinnamon cozy warm comforting tea"),
    ("refresher",      "refresher",    "summer",  "cold", 4.75, "mid",  "Strawberry Acai Refresher fruity strawberry summer bright refreshing iced light energizing"),
    ("bacon_gouda",    "food",         "all",     "hot",  4.95, "high", "Bacon Gouda breakfast sandwich savory cheese morning food pairing filling"),
    ("croissant",      "food",         "all",     "warm", 3.75, "high", "Butter Croissant flaky buttery pastry morning food pairing light"),
    ("cake_pop",       "food",         "all",     "cold", 2.95, "high", "Birthday Cake Pop sweet treat colorful fun snack indulgent"),
    ("tumbler",        "merch",        "all",     "na",   24.95,"high", "Reusable Cup Tumbler stainless steel gift collectible eco sustainable merchandise"),
]
PROD_IDS   = [p[0] for p in CATALOG]
PROD_DESCS = [p[6] for p in CATALOG]
PROD_META  = {p[0]: dict(category=p[1], season=p[2], temp=p[3], price=p[4], margin=p[5]) for p in CATALOG}
MARGIN_W   = {"low": 0.2, "mid": 0.5, "high": 0.9}

# ----------------------------------------------------------------------------
# 2. Synthetic users built from archetypes (so natural clusters exist)
# ----------------------------------------------------------------------------
ARCHETYPES = {
    "fall_seasonal":   "pumpkin spice fall autumn seasonal cozy warm latte cinnamon morning ritual",
    "cold_brew_reg":   "cold brew iced refreshing afternoon bold smooth everyday nitro",
    "tea_wellness":    "matcha green tea wellness healthy calm earthy chai cozy",
    "holiday_festive": "peppermint mocha holiday festive winter caramel cozy seasonal chocolate",
    "summer_fruity":   "refresher strawberry fruity summer bright light energizing iced",
    "commuter_food":   "breakfast sandwich croissant morning food coffee latte quick everyday filling",
    "classic_simple":  "pike place brewed black coffee classic simple everyday morning",
}
ARCH_NAMES = list(ARCHETYPES.keys())
LIFECYCLES = ["new", "loyal", "lapsed", "vip"]
LIFE_P     = [0.20, 0.45, 0.25, 0.10]
DAYPARTS   = ["morning", "afternoon", "evening"]

def make_users(n=200):
    users = []
    for i in range(n):
        arch = ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]
        base = ARCHETYPES[arch].split()
        # take a noisy subset of the archetype terms + occasional cross-interest noise
        k = RNG.integers(5, len(base) + 1)
        terms = list(RNG.choice(base, size=k, replace=False))
        if RNG.random() < 0.25:  # 25% have a secondary interest (realistic messiness)
            other = ARCHETYPES[ARCH_NAMES[RNG.integers(len(ARCH_NAMES))]].split()
            terms += list(RNG.choice(other, size=2, replace=False))
        users.append(dict(
            user_id=f"u{i:04d}",
            archetype=arch,                      # ground truth, for sanity-check only
            interest_text=" ".join(terms),
            lifecycle=RNG.choice(LIFECYCLES, p=LIFE_P),
            daypart=RNG.choice(DAYPARTS),
            price_band=RNG.choice(["low", "mid", "high"], p=[0.3, 0.5, 0.2]),
        ))
    return users

# ----------------------------------------------------------------------------
# 3. Embed: shared TF-IDF space over user interests + product descriptions
# ----------------------------------------------------------------------------
def build_embeddings(users):
    corpus = [u["interest_text"] for u in users] + PROD_DESCS
    vec = TfidfVectorizer(min_df=1, stop_words="english")
    X = vec.fit_transform(corpus).toarray()
    n = len(users)
    return X[:n], X[n:], vec  # user_vecs, prod_vecs, vectorizer

# ----------------------------------------------------------------------------
# 4. Segment: facet by lifecycle, KMeans within each facet on interest vectors
# ----------------------------------------------------------------------------
def segment(users, user_vecs, min_seg=8, max_k=4):
    by_life = defaultdict(list)
    for idx, u in enumerate(users):
        by_life[u["lifecycle"]].append(idx)

    segments = []
    for life, idxs in by_life.items():
        idxs = np.array(idxs)
        n = len(idxs)
        if n < min_seg:                          # too few -> single segment (or fallback)
            segments.append((f"seg_{life}_all", life, idxs))
            continue
        k = max(1, min(max_k, n // min_seg))
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(user_vecs[idxs])
        for c in range(k):
            members = idxs[km.labels_ == c]
            if len(members) == 0:
                continue
            segments.append((f"seg_{life}_{c}", life, members))
    return segments

# ----------------------------------------------------------------------------
# 5. Match: hybrid retrieve (filters) + rank per segment
# ----------------------------------------------------------------------------
def top_terms(vec, centroid, topn=6):
    inv = np.array(vec.get_feature_names_out())
    order = np.argsort(centroid)[::-1]
    return [t for t in inv[order][:topn]]

def lifecycle_fit(meta, life):
    # new -> flagship/core; lapsed -> familiar core; vip -> premium/high; loyal -> seasonal ok
    cat = meta["category"]
    if life == "new":    return 0.9 if cat in ("core_bev", "seasonal_bev") else 0.5
    if life == "lapsed": return 0.9 if cat in ("core_bev", "cold_coffee") else 0.5
    if life == "vip":    return 0.9 if meta["margin"] == "high" else 0.6
    return 0.8  # loyal: open to most

def match_segment(centroid, life, prod_vecs, k=3):
    sims = cosine_similarity(centroid.reshape(1, -1), prod_vecs)[0]
    scored = []
    for j, pid in enumerate(PROD_IDS):
        meta = PROD_META[pid]
        if meta["category"] == "merch":           # filter: merch only for gifting campaigns (skip here)
            continue
        score = (0.60 * sims[j]
                 + 0.25 * lifecycle_fit(meta, life)
                 + 0.15 * MARGIN_W[meta["margin"]])
        scored.append((pid, score, sims[j]))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]

# ----------------------------------------------------------------------------
# 6. Run + report
# ----------------------------------------------------------------------------
def main():
    users = make_users(200)
    user_vecs, prod_vecs, vec = build_embeddings(users)
    segments = segment(users, user_vecs)

    lines = []
    def out(s=""):
        print(s); lines.append(s)

    out("=" * 78)
    out("PROJECT AD — SEGMENTATION + MATCHING SPIKE")
    out(f"{len(users)} synthetic users · {len(PROD_IDS)} products · {len(segments)} segments")
    out("=" * 78)

    purity_scores = []
    for sid, life, members in sorted(segments, key=lambda s: -len(s[2])):
        centroid = user_vecs[members].mean(axis=0)
        terms = top_terms(vec, centroid)
        # sanity: dominant ground-truth archetype share within the segment ("purity")
        archs = Counter(users[m]["archetype"] for m in members)
        dom_arch, dom_n = archs.most_common(1)[0]
        purity = dom_n / len(members)
        purity_scores.append(purity)
        top = match_segment(centroid, life, prod_vecs)

        out(f"\n▶ {sid}  | size={len(members):3d} | lifecycle={life}")
        out(f"   interest centroid: {', '.join(terms)}")
        out(f"   dominant archetype: {dom_arch} ({purity:.0%} of segment)")
        out(f"   top products:")
        for pid, sc, sim in top:
            m = PROD_META[pid]
            out(f"      - {pid:14s} score={sc:.3f} (sim={sim:.3f}, {m['category']}, {m['season']}, margin={m['margin']})")

    out("\n" + "=" * 78)
    out("SANITY CHECK")
    out(f"   mean segment purity (dominant archetype share): {np.mean(purity_scores):.0%}")
    out(f"   segments above 60% purity: {sum(p>0.6 for p in purity_scores)}/{len(purity_scores)}")
    out("   (high purity => clustering grouped similar users => one ad per segment is sound)")
    out("=" * 78)

    with open("spike_results.txt", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
