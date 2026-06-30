"""
Product Discovery Agent — pick the product that matches a segment's interest.
============================================================================
The product is NOT hardcoded. It is RETRIEVED by embedding similarity between
the segment's interest and a product-description table.

HOW (now): the catalog lives in `product_catalog.json` (one row per product,
per brand). `discover_candidates()` embeds the interest query and every product
description into a shared vector space and ranks products by cosine similarity,
breaking ties by how central the product is to the brand. This reuses the
matcher from `Starbucks/spike_segmentation_matching.py`.

STAND-IN: the embedding step (`_embed`) uses TF-IDF as an offline, deterministic
stand-in for a hosted embedding model — exactly as the spike does. To go to
production, swap the body of `_embed()` for a call to a real embedding model
(same contract: a list of texts -> one dense row vector each). Nothing else in
this module or the pipeline changes; the return shape is identical.
"""
import json
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "product_catalog.json")


def _load_catalog(brand="Starbucks"):
    """Load the product-description table for a brand (per-brand tenant isolation)."""
    with open(_CATALOG_PATH) as fp:
        data = json.load(fp)
    if brand not in data:
        raise KeyError(f"No catalog for brand {brand!r}; have {[b for b in data if not b.startswith('_')]}")
    return data[brand]


def _doc(p):
    """The text we embed for a product: name + tags + flavor + descriptors."""
    return f"{p['name']} {' '.join(p['tags'])} {p['flavor']} {p['descriptors']}"


def _embed(texts):
    """STAND-IN embedding: TF-IDF vectors over a shared space (offline, deterministic).

    Drop in a hosted embedding model here — the only contract is:
    take a list of strings, return one row vector per string (np.ndarray, shape
    [len(texts), dim]). The caller computes cosine similarity over the result.
    """
    vec = TfidfVectorizer(min_df=1, stop_words="english")
    return vec.fit_transform(texts).toarray()


def _as_palette(palette):
    """JSON stores palette as lists; the pipeline expects tuples-of-RGB-tuples."""
    return tuple(tuple(c) for c in palette)


def discover_candidates(interest, brand="Starbucks", k=3):
    """Return products ranked by embedding similarity to the segment interest.

    Same return shape as before: a list of product dicts, each with all catalog
    fields plus `sim` (float cosine score, 0..1) and `why` (human reason).
    """
    catalog = _load_catalog(brand)
    # Embed the interest query and every product description in one shared space.
    matrix = _embed([interest] + [_doc(p) for p in catalog])
    query_vec, prod_vecs = matrix[:1], matrix[1:]
    sims = cosine_similarity(query_vec, prod_vecs)[0]

    scored = list(zip(sims, catalog))
    # Rank by interest similarity; break ties by how central the product is to the brand.
    scored.sort(key=lambda x: (x[0], x[1]["centrality"]), reverse=True)

    out = []
    for sim, p in scored[:k]:
        out.append({
            **p,
            "palette": _as_palette(p["palette"]),
            "sim": round(float(sim), 2),
            "why": f"embedding match (cosine sim={sim:.2f}) to interest ['{interest}']",
        })
    return out


if __name__ == "__main__":
    # Show how the RETRIEVED product changes across different audience segments.
    segments = [
        "fall seasonal ritual morning autumn cozy",
        "cold brew iced refreshing afternoon bold",
        "matcha green tea wellness calm earthy",
        "peppermint holiday festive winter chocolate",
        "strawberry fruity summer bright refreshing",
        "apple cinnamon brown sugar",
    ]
    print(f"{'segment interest':42s}  ->  top product (sim)   [runners-up]")
    print("-" * 92)
    for interest in segments:
        top3 = discover_candidates(interest, k=3)
        best = top3[0]
        runners = ", ".join(f"{p['product_id']}({p['sim']})" for p in top3[1:])
        print(f"{interest:42s}  ->  {best['name'][:26]:26s} ({best['sim']})   [{runners}]")
