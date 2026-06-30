# Audience Segmentation & Scaling — Design

*How Project AD serves thousands of users without generating a unique ad per person. We generate **per segment**: cluster users with similar data into cohorts, generate one ad (or a small variant set) per cohort, and distribute it to every member. This is the layer that makes the economics and human review feasible.*

Status: Draft · Pairs with `Product-Matching-and-Recommendation.md`, `Personalization-Design-System.md`, `Ad-Spec-Schema.md`

---

## 1. The problem this solves

One ad per user does not scale:
- **Cost** — every ad is ≥1 image-model call + LLM calls. 100k users = 100k generations. Untenable.
- **Human review** — the agency-quality bar needs a human gate. No team reviews 100k ads.
- **No benefit** — most users are near-duplicates in what would make them respond. Generating a separate ad for each is waste, not personalization.

**The reframe:** personalization happens at the **segment** level. A segment is a group of users who are similar enough that *the same ad works for all of them*. We generate for the segment; we distribute to the members.

```
 100,000 users  ──cluster──▶  ~80 segments  ──generate──▶  ~80 ads (×variants)
                                                              │
                                                   distribute each ad to its segment's members
```

Generation and review scale with the **number of segments**, not the number of users. Segments grow far slower than users (sub-linear) — 100k users might need 50–150 segments, and 1M users might need only a few hundred.

---

## 2. Where segmentation sits in the pipeline

```
 all user profiles
        │
        ▼
 [ 1. SEGMENT ]  cluster similar users → cohorts, each with a representative profile (centroid)
        │
        ▼   (per segment, not per user)
 [ 2. PRODUCT MATCH ]  retrieve→rank against the segment's representative profile
        │
        ▼
 [ 3. GENERATE ]  art-director → ad spec → render → QC → human review   (once per segment)
        │
        ▼
 [ 4. DISTRIBUTE ]  serve the approved ad to every member of the segment
        │
        ▼
 [ 5. MEASURE ]  per-member outcomes roll back up to the segment → refine
```

The product-matching and generation stages already designed now run **once per segment** instead of once per user. Almost nothing in them changes except the input is a segment representative, not an individual.

---

## 3. What a segment is

```yaml
segment_id: seg_sbux_fall_am_loyal
brand_id: starbucks
size: 14820                         # members in this segment
# --- representative (centroid) profile: drives matching & generation ---
representative:
  lifecycle: "loyal"
  dominant_interests: ["fall seasonal drinks", "morning ritual"]
  interest_vectors: [ ... ]         # centroid of members' interest vectors
  price_band: "mid"
  common_context: { season: "fall", daypart: "morning" }
  rewards_member: true
# --- cohesion & metadata ---
cohesion: 0.82                      # how tight the cluster is (0–1); low → split it
confidence: "behavioral"            # dominant signal source for this segment
created_at: "2026-06-30"
served_ad_ids: ["sbux-a-0001"]
```

A segment carries a **representative profile** — typically the centroid of its members' vectors plus the modal/most-common structured attributes. That representative is what flows into product matching and the art-director, exactly where an individual profile did before.

---

## 4. Stage 1 — Segmentation (how users are grouped)

Two complementary methods; use both:

**A. Embedding clustering (semantic).** Cluster users by their interest vectors (e.g. k-means / HDBSCAN over the profile vectors). Groups people with similar *taste* even if they never share an explicit attribute. HDBSCAN is attractive because it finds natural cluster count and leaves genuine outliers unclustered (handled in §6).

**B. Structured faceting (rules).** Partition by hard attributes that *must* differ the ad — lifecycle (new/loyal/lapsed), eligibility, region/language, channel. These are deterministic splits, not learned.

**Combine them:** facet first on the attributes that change the ad's strategy (a loyal and a lapsed user should never share an ad), then cluster semantically *within* each facet. So a segment is "loyal × morning × {fall-seasonal taste cluster}." This keeps segments both strategically and aesthetically coherent.

---

## 5. The granularity tradeoff (the key tuning knob)

Number of segments is the dial between personalization and cost:

| More segments (finer) | Fewer segments (coarser) |
|---|---|
| Tighter personalization, higher relevance | Blunter, more generic ads |
| More generations + more human review (cost ↑) | Cheaper, faster, less review |
| Risk: segments too small to justify a generation | Risk: averaging washes out what made people respond |

**Controls:**
- **Min segment size** — don't generate for a cohort below N members (e.g. 500); merge it into its nearest neighbor or the fallback. Generation cost must be justified by reach.
- **Max segments / budget cap** — a hard ceiling per run; lowest-value segments fall back to a parent ad.
- **Cohesion floor** — if a cluster is too loose (low cohesion), the centroid ad won't fit anyone; split or drop it.
- **Value-weighting** — spend the segment budget where it pays: high-value/large/high-intent cohorts get finer segmentation and more variants; the long tail gets coarse, shared, or fallback ads.

> Rule of thumb: start coarse, measure, and split only the segments where finer targeting demonstrably lifts response. Don't pre-optimize to thousands of tiny segments.

---

## 6. Edge cases

- **Outliers / unclustered users** — people who don't fit any cohort get the brand's **fallback ad** (no-data/brand-essence path from the rulebook), not their own generation.
- **Tiny segments** — below min size → merged up or fallback.
- **New users with no data** — routed to the cold-start/fallback segment until enough signal accrues to cluster them.
- **Multi-interest users** — a person can belong to more than one segment for *different* products/campaigns; that's fine, it's resolved at serving time by campaign/eligibility.
- **Drift** — interests and the catalog change, so segments are **recomputed on a schedule** (e.g. daily/weekly) or on significant signal change, not once.

---

## 7. Variants per segment (optional, controlled)

Within a segment you may generate a **small set of variants** (e.g. 2–3 different concepts or formats) and either A/B them or match sub-context (feed vs. story aspect ratio). This adds richness without exploding cost, because it's a handful of variants over an *approved segment*, not per-user generation. Variant count is part of the budget knob in §5.

---

## 8. Distribution & serving

- Each approved segment ad is stored with its `segment_id` and member list (or a re-evaluable membership rule).
- At serve time, a user is mapped to their current segment → served that segment's approved ad (and variant, if A/B).
- Membership can be **static** (snapshot at segmentation time) or **dynamic** (re-evaluated at request time against the rule). Dynamic is more current but costlier; choose per channel.
- A user whose segment has no approved ad yet falls back gracefully.

---

## 9. Measurement & the flywheel

Outcomes are logged **per member** (impression/click/conversion) but **aggregated per segment**. This feeds:
1. **Segment value scoring** — which segments convert → get finer granularity and more budget next run.
2. **Re-segmentation** — merge segments that behave identically; split ones with high internal variance in response.
3. **The product-matching re-ranker and the quality feedback loop** — same logged outcomes serve all three.

So segmentation isn't static — it's continuously re-tuned by what actually performs, concentrating spend where personalization pays.

---

## 10. Economics illustration (rough)

| Users | Naive (per-user) | Segmented (per-cohort) |
|---|---|---|
| 1,000 | 1,000 generations + 1,000 reviews | ~30 segments → 30 ads |
| 100,000 | 100,000 generations | ~100 segments → 100 ads |
| 1,000,000 | impossible | ~300 segments → 300 ads |

Generation and review cost track segments, which grow sub-linearly with users. This is what makes agency-quality + human review viable at scale.

---

## 11. Impact on existing docs
- **Ad-Spec (v0.2):** the spec is generated for a `segment_id`; its `personalization` block describes the **segment representative**, not an individual. (Added in v0.2.)
- **Product-Matching:** runs once per segment, against the representative profile. The data model and flow are unchanged — the input is a centroid instead of a person.
- **Personalization rulebook:** rules now read segment-level signals; literalness drops accordingly (a segment ad addresses a *group*, so literal "your saved item" is rarely valid — segment ads skew inferential by nature).
- **Quality system:** human review volume = segment volume, which is what makes the human gate affordable.

---

## 12. Open questions / spike
- Clustering algorithm + distance metric: k-means vs HDBSCAN on interest vectors — test cluster quality on real-ish data.
- Re-segmentation cadence: daily vs. weekly vs. event-driven.
- Min segment size and max-segment budget defaults per brand.
- Static vs. dynamic membership per channel.
- How literal can a *segment* ad get before it misfits members — set the literalness ceiling for grouped ads.

**Suggested spike:** generate ~200 synthetic Starbucks user profiles, facet by lifecycle, cluster within facets, and check whether the resulting segments are coherent enough that one ad per segment feels right. Pairs with the catalog-embedding spike from `Product-Matching`.
