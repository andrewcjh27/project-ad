# Product-Matching & Recommendation — Design

*The pipeline stage that selects **which product(s)** to advertise to a given person, before any ad is designed. It turns audience signals + a catalog into a small, ranked set of high-fit product candidates that the art-director LLM then turns into ad specs.*

Status: Draft · Pairs with `Personalization-Design-System.md`, `Ad-Spec-Schema.md`, `Project-AD-Planning.md`

---

## 1. Where this sits in the pipeline

```
 audience signals ──▶  [ 1. RETRIEVE ]  ──▶  [ 2. RANK ]  ──▶  top-K product candidates
   (profile)            hybrid:                re-rank by                │
                        filters + vectors      business + behavior       │
                                                                         ▼
                           brand package + personalization rulebook ──▶ ART-DIRECTOR LLM
                                                                         │  (final pick + concept)
                                                                         ▼
                                                                     AD SPEC ──▶ render ──▶ QC
```

Two-stage **retrieve-then-rank**, then an LLM final selection. Each stage is cheaper than the next, so we narrow the catalog fast and spend reasoning only on a handful of finalists.

---

## 2. Core principle: hybrid, not pure-vector

Audience and product data each split into two kinds — **structured** (facts) and **semantic** (fuzzy). They're matched differently. This mirrors the hard/soft split used in the brand-identity layer.

| | Structured (facts) | Semantic (fuzzy) |
|---|---|---|
| **Audience** | gender-target preference, price band, size, location, language, lifecycle | interests & vibe ("outdoorsy, minimalist, wellness"), aesthetic taste |
| **Product** | category, color, price, size, gender-fit, in-stock, season tag, margin | description, story, mood, use-case |
| **Matched by** | **filters / features** (exact, deterministic) | **vector similarity** (embeddings) |

> Never embed a structured fact as fuzzy text. "Likes green" and "female" are filters, not vectors — embedding them is imprecise and, for demographics, risky (see §7). Embeddings are reserved for genuinely semantic taste.

---

## 3. Data model

### 3.1 Product record (one per SKU)
```yaml
product_id: sbux-psl-grande
brand_id: starbucks
# --- structured (filters/features) ---
category: "seasonal_beverage"
subcategory: "espresso"
season_tags: ["fall"]
price: 5.95
color_tags: ["orange", "cream"]
gender_fit: "any"
in_stock: true
margin_tier: "high"
eligibility: ["rewards", "general"]    # channel/audience eligibility
# --- semantic (embedded) ---
description: "Pumpkin Spice Latte — espresso with pumpkin, cinnamon, nutmeg, steamed milk and foam. A warm, nostalgic autumn ritual."
embedding: [ ... ]                      # vector of `description` (+ optional attributes text)
embedding_model: "text-embed-x@v1"     # pin model + version
embedding_updated_at: "2026-06-30"
```

### 3.2 Audience profile (one per person, rebuilt on signal change)
```yaml
audience_id: u_8831
brand_id: starbucks
# --- structured (filters) ---
price_band: "mid"
location: "US-CA"
language: "en"
lifecycle: "loyal"          # new | loyal | lapsed | vip | churning
rewards_member: true
# --- semantic: MULTIPLE interest vectors, never one average ---
interests:
  - { label: "fall seasonal drinks", vector: [ ... ], confidence: 0.9, source: "behavioral" }
  - { label: "morning ritual",       vector: [ ... ], confidence: 0.8, source: "behavioral" }
  - { label: "cozy / comfort",       vector: [ ... ], confidence: 0.5, source: "inferred" }
# --- behavioral history (for ranking, not retrieval) ---
recent_categories: ["espresso", "cold_brew"]
favorites: ["latte"]
```
> **Multiple interest vectors**, each with a confidence and source. Retrieval queries each separately — never an averaged user vector (which points at no real product). Confidence + source gate how literally we personalize downstream (per rulebook §3).

---

## 4. Stage 1 — Retrieve (hybrid candidate generation)

For each interest vector above a confidence floor:

1. **Apply hard filters first** (cheap, shrinks the search space): `brand_id`, `in_stock = true`, `eligibility` matches channel/audience, `price` within band, structured prefs (e.g. `color_tags ∩ prefs`, `gender_fit` compatible), `season_tags` if seasonal.
2. **Vector search** the filtered set: nearest products to that interest vector, top-N per interest.
3. **Merge** candidate lists across interests, dedupe, keep similarity scores and which interest each came from.

Output: a candidate pool (e.g. 50–100 products) with `{product_id, best_interest_match, similarity, matched_interests[]}`. No fixed global similarity threshold here — we over-retrieve and let ranking decide.

> Why filters first: it makes vector search faster and prevents semantically-similar-but-ineligible matches (out of stock, wrong price, wrong channel).

---

## 5. Stage 2 — Rank (re-rank the candidates)

Embeddings give *topical fit*; ranking adds everything embeddings can't see. Score each candidate on a weighted blend (weights tunable per brand, learned over time):

| Signal | Why |
|---|---|
| Semantic similarity (from retrieval) | topical interest fit |
| Interest confidence × source weight | trust expressed > behavioral > inferred |
| Behavioral propensity | bought/browsed this category recently → higher |
| Business value | margin tier, inventory push, strategic priority |
| Seasonality / timeliness | in-season, event-relevant |
| Brand-fit | product central to brand vs. long-tail |
| Lifecycle fit | new→flagship, lapsed→favorite, vip→premium (rulebook §4) |
| Diversity penalty | avoid 5 near-identical SKUs in the candidate set |

Output: **top-K finalists** (e.g. 3–5), ranked, each carrying its score breakdown and matched interests for traceability.

> Day 1, weights are hand-set and similarity-led. As conversion data accumulates, the re-ranker is trained on **what actually converted** (§8) — behavior gradually outweighs raw semantic similarity.

---

## 6. Stage 3 — Handoff to the art-director

The art-director LLM receives the top-K finalists (not just the #1), plus the brand package and personalization rulebook, and makes the **final selection with reasoning**. It can override pure rank for brand fit or creative coherence, and it records *why*.

Handoff payload per finalist:
```json
{
  "product_id": "sbux-psl-grande",
  "rank": 1,
  "score_breakdown": { "similarity": 0.82, "behavioral": 0.7, "business": 0.6, "lifecycle_fit": 0.9 },
  "matched_interests": ["fall seasonal drinks", "morning ritual"],
  "structured": { "category": "seasonal_beverage", "season_tags": ["fall"], "price": 5.95 }
}
```

The art-director's choice + reasoning populate the ad spec's `personalization` block:
```json
"personalization": {
  "signals_used": ["interest:fall seasonal drinks", "behavioral:morning_espresso", "lifecycle:loyal"],
  "inference": "loyal AM regular receptive to a seasonal upgrade of their ritual",
  "selected_product": "sbux-psl-grande",
  "selection_reason": "highest lifecycle + interest fit; central seasonal hero",
  "literalness": "inferential"
}
```
This makes every product choice **explainable** end-to-end — essential for the human reviewer and the feedback loop.

---

## 7. Guardrails (bias, fairness, privacy)

- **Prefer behavioral/expressed signals over demographic inference.** Targeting on inferred protected attributes (gender, age, etc.) is a legal and brand risk in advertising. Use them, if at all, only as soft structured prefs the user effectively declared — never as the primary match driver. Behavioral signals are both higher-confidence and safer.
- **No protected-attribute embedding.** Don't encode demographics into vectors where they silently drive matches.
- **Eligibility filter is mandatory** — products restricted by channel, region, or audience must be filtered in Stage 1, not caught later.
- **Confidence gates literalness** downstream (rulebook §3/§6): low-confidence/inferred matches stay inferential in the ad.
- **Auditability:** every selection logs its filters, matched interests, scores, and the art-director's reason. If asked "why was this person shown this," the system can answer.
- **Fallback:** if no candidate clears a minimum quality bar after ranking, fall back to the brand's flagship/seasonal hero (the no-data path) rather than forcing a weak match.

---

## 8. Feedback loop (semantic → behavioral over time)

Log, per served ad: the candidate set, the chosen product, the scores, and the **outcome** (impression, click, conversion). Uses:

1. **Re-ranker training** — learn the weight blend that predicts conversion, replacing hand-set weights.
2. **Embedding fine-tuning** (later) — adapt product/interest embeddings toward what actually converts, not just text similarity.
3. **Threshold/quality calibration** — set the minimum-fit fallback trigger from real data.
4. **Brand-level tuning** — different brands learn different weightings.

This is the same feedback flywheel as the quality system — every served ad makes selection smarter.

---

## 9. Tech choices

| Piece | Choice | Note |
|---|---|---|
| Embeddings | Hosted embedding model behind an adapter | Pin model + version per vector; re-embed on model change. |
| Vector store | pgvector (start) or dedicated (Pinecone/Qdrant) at scale | Per-brand isolation, metadata filters for the hard filters. |
| Filtering | Metadata filters in the vector query / SQL pre-filter | Structured facts live as columns/metadata, not vectors. |
| Re-ranker | Rules/weighted score (v1) → learned model (v2) | Start simple, make it learnable. |
| Final selection | Art-director LLM | Reasoned pick from top-K. |
| Logging | Append-only event log keyed by ad_id | Feeds §8. |

---

## 10. Open questions / spike before building
- Embedding granularity: embed description only, or description + structured-attribute text? Test retrieval quality both ways.
- How many interest vectors per person before diminishing returns?
- Cold-start catalog: products with thin descriptions — enrich before embedding?
- Per-brand vs. shared embedding space (per-brand isolation says per-brand; cost says shared — decide).
- Minimum-fit fallback threshold: how low is "too weak to advertise"?

**Suggested first spike:** embed the Starbucks catalog, build 2–3 audience profiles (the loyal/lapsed/new test personas), run retrieve→rank, and eyeball whether the top-K products make sense before wiring the art-director. Same lightweight validation approach as the ad-spec spike.
