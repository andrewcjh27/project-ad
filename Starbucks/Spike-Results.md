# Spike Results — Segmentation + Product Matching

*Validation run of the pre-generation pipeline: 200 synthetic Starbucks users → facet by lifecycle → cluster on interest embeddings → hybrid retrieve+rank → top-3 products per segment. Run via `spike_segmentation_matching.py`; raw output in `spike_results.txt`.*

> **Note:** embeddings use TF-IDF as an offline stand-in for a real embedding model. The *pipeline mechanics* (facet → cluster → centroid → retrieve → rank) are exactly what production uses; only the embedding backend swaps.

---

## Verdict: the approach holds

200 users collapsed into **13 segments** — confirming the scaling thesis: we'd generate ~13 ads, not 200. The matches are sensible and on-brand:

| Segment (representative) | Lifecycle | Top product | Reads right? |
|---|---|---|---|
| fall / pumpkin / cinnamon | loyal | **PSL** | ✅ |
| peppermint / holiday / mocha | lapsed | **Peppermint Mocha** | ✅ |
| cold / iced / nitro / bold | loyal | **Nitro / Cold Brew** | ✅ |
| classic / simple / pike / black | new | **Pike Place** | ✅ |
| breakfast / sandwich / food | new | **Bacon Gouda** | ✅ |
| matcha / green tea / wellness | new | **Matcha Latte** | ✅ |

Lifecycle faceting also behaves: `new` segments skew to flagship/core, `lapsed` toward familiar core, `vip` toward high-margin seasonal — exactly the rulebook intent.

**Sanity metric — segment purity** (share of a segment that is one true archetype): **mean 75%**, with **8/13 segments above 60%**, and several at **100%**. High purity means the clustering really did group similar people, so *one ad per segment is justified*.

---

## What the spike also exposed (the useful part)

1. **A few loose segments.** `seg_new_0` blended tea + fruity (44% purity); a couple of others mixed. Cause: small per-facet user counts forced a low cluster count (`k`). **Fix:** a cohesion floor — when a cluster's internal spread is too high, split it or route stragglers to fallback (already specified in `Audience-Segmentation-and-Scaling.md §6`). The spike confirms we need that floor, not just nice-to-have.

2. **Cross-interest noise propagates.** The 25% of users given a secondary interest occasionally pulled a centroid off (e.g. a stray seasonal product in a cold-brew segment's #3 slot). **Fix:** multi-interest users should belong to *multiple* segments (per-campaign), not be averaged into one — matches the design's "multiple interest vectors, never one average" rule.

3. **Ranking weights matter.** Margin weighting (0.15) nudged high-margin seasonal items into 2nd/3rd slots even for non-seasonal segments. That's tunable and is exactly what the conversion feedback loop should learn rather than hand-set.

4. **Filters earn their keep.** Excluding `merch` (gifting-only) at the filter stage kept tumblers out of beverage segments cleanly — validating filters-before-vectors.

---

## Implication for the build

The pre-generation half of the pipeline is **sound and cheap to run**. Before wiring expensive generation, the only adds the spike proves we need are: a **cohesion floor** on clusters, **multi-segment membership** for multi-interest users, and **learned ranking weights** over time. None are blockers.

**Recommended next step:** swap the TF-IDF stand-in for a real embedding model and re-run on a larger synthetic set to confirm purity holds, then connect the top segment → the art-director → ad-spec v0.2 → first rendered Starbucks ad (Phase 0 goal).

---

## Files
- `spike_segmentation_matching.py` — the runnable spike.
- `spike_results.txt` — full raw output (all 13 segments).
