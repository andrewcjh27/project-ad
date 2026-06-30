"""
Project AD — Brand Memory (exemplar retrieval for the Art Director)
===================================================================
Conditions the Art Director / Copywriter on REAL past on-brand ads instead of
hand-written prompt text alone. At generation time we retrieve the `k` most
relevant past ads for this brand + segment interest and feed them to the LLM as
few-shot exemplars ("here's how we've done autumn before"). This is the
"learn to retrieve" approach: no model training, works with a small corpus.

WHERE IT FITS: this is the SOFT-GUIDANCE layer only — exemplars inform voice and
concept. Brand hard-rules (colors / fonts / logo / legal) stay deterministic and
are enforced by `BrandGuardian`; we deliberately embed only concept/copy fields,
never hex/font/logo.

STORE (per-brand, tenant-isolated), two files under `brand_memory/`:
  - `<brand>.seed.jsonl`  committed, hand-authored stand-in exemplars (read-only).
  - `<brand>.jsonl`       runtime memory, grown by `remember()` from APPROVED ads
                          (gitignored). Quality-filtered: only Critic-approved ads
                          are remembered, so the memory compounds toward the
                          feedback loop in Project-AD-Planning.md §5.4.

EMBEDDING: reuses `product_discovery._embed` — the single embedding seam (TF-IDF
stand-in now, hosted model later). Swapping `_embed` upgrades product discovery
AND brand memory together; nothing here changes.
"""
import os
import json
import hashlib

from sklearn.metrics.pairwise import cosine_similarity

from product_discovery import _embed   # single shared embedding seam

_MEMORY_DIR = os.path.join(os.path.dirname(__file__), "brand_memory")
_COLD_START_FLOOR = 2   # below this many exemplars, retrieval returns [] (no signal)


def _seed_path(brand_id):
    return os.path.join(_MEMORY_DIR, f"{brand_id}.seed.jsonl")


def _learned_path(brand_id):
    return os.path.join(_MEMORY_DIR, f"{brand_id}.jsonl")


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_store(brand_id):
    """Committed seed exemplars + runtime-learned exemplars (tenant-isolated)."""
    return _read_jsonl(_seed_path(brand_id)) + _read_jsonl(_learned_path(brand_id))


def _doc(ex):
    """Text we embed for an exemplar — CONCEPT/COPY fields only (never brand hard-rules)."""
    return " ".join(str(ex.get(k, "")) for k in
                    ("headline", "subhead", "copy_angle", "messaging_pillar",
                     "image_prompt", "interest"))


def _content_hash(headline, image_prompt):
    return hashlib.sha1(f"{headline}\n{image_prompt}".encode()).hexdigest()[:10]


def retrieve_exemplars(interest, brand_id="starbucks", k=3):
    """Return the `k` past ads most similar to `interest` (cosine over `_embed`).

    Same return-shape discipline as product_discovery.discover_candidates: a list
    of dicts, each with the exemplar's concept/copy fields plus `sim` and
    `exemplar_id`. Cold-start safe: returns [] when the store has too little signal.
    """
    store = _load_store(brand_id)
    if len(store) < _COLD_START_FLOOR:
        return []

    matrix = _embed([interest] + [_doc(e) for e in store])
    query_vec, ex_vecs = matrix[:1], matrix[1:]
    sims = cosine_similarity(query_vec, ex_vecs)[0]

    scored = sorted(zip(sims, store), key=lambda x: x[0], reverse=True)
    out = []
    for sim, e in scored[:k]:
        out.append({
            "exemplar_id": e.get("exemplar_id", ""),
            "headline": e.get("headline", ""),
            "subhead": e.get("subhead", ""),
            "copy_angle": e.get("copy_angle", ""),
            "messaging_pillar": e.get("messaging_pillar", ""),
            "image_prompt": e.get("image_prompt", ""),
            "sim": round(float(sim), 2),
        })
    return out


def remember(spec, brand_id="starbucks"):
    """Append an APPROVED ad's concept/copy to the runtime memory (deduped).

    Call this only when the Critic verdict is `approve`. Stores concept/copy
    fields only — the same things `_doc` embeds — never brand hard-rules. Deduped
    by a content hash of (headline + image prompt) so re-running stays idempotent.
    """
    def _content(el_id):
        return next((e.get("content", "") for e in spec.get("elements", [])
                     if e.get("id") == el_id), "")

    headline = _content("headline") or spec.get("concept", {}).get("big_idea", "")
    imagery = spec.get("canvas", {}).get("imagery", [{}])
    image_prompt = imagery[0].get("prompt", "") if imagery else ""
    h = _content_hash(headline, image_prompt)

    existing = _read_jsonl(_learned_path(brand_id))
    if any(_content_hash(r.get("headline", ""), r.get("image_prompt", "")) == h for r in existing):
        return None   # already remembered

    row = {
        "exemplar_id": f"gen_{h}",
        "brand_id": brand_id,
        "interest": spec.get("_segment", {}).get("dominant_interest", ""),
        "product_id": spec.get("personalization", {}).get("selected_product", ""),
        "messaging_pillar": spec.get("concept", {}).get("messaging_pillar", ""),
        "copy_angle": spec.get("concept", {}).get("copy_angle", ""),
        "headline": headline,
        "subhead": _content("subhead"),
        "image_prompt": image_prompt,
    }
    os.makedirs(_MEMORY_DIR, exist_ok=True)
    with open(_learned_path(brand_id), "a") as fp:
        fp.write(json.dumps(row) + "\n")
    return row["exemplar_id"]


if __name__ == "__main__":
    # Show which PAST ADS the Art Director would be shown for each segment interest.
    interests = [
        "fall seasonal ritual morning autumn",
        "cold brew iced refreshing afternoon bold",
        "matcha green tea wellness calm earthy",
        "peppermint holiday festive winter chocolate",
        "strawberry fruity summer bright refreshing",
        "apple cinnamon brown sugar",
    ]
    print(f"{'segment interest':42s}  ->  top exemplars (sim)")
    print("-" * 92)
    for interest in interests:
        top = retrieve_exemplars(interest, k=3)
        shown = ", ".join(f"{e['exemplar_id']}({e['sim']})" for e in top)
        print(f"{interest:42s}  ->  {shown}")
