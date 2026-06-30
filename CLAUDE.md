# Project AD — context for Claude Code

AI system that designs **personalized, brand-on-identity ads** (image/poster) for an
audience **segment**, using AI to retrieve a product, generate the imagery prompt &
copy, composite a finished ad, QC it against brand rules, and hand off to Figma for
designer retouch. Quality bar: top agency / brand campaign. Scope now: **image + poster**
(video deferred). Build path: internal tool now, SaaS-ready architecture underneath.

## How it works (pipeline)
```
audience SEGMENT
  → product_discovery   retrieve product by interest similarity (web-sourced now; catalog later)
  → llm_agent           Art Director GENERATES image prompt; Copywriter GENERATES copy (from data)
  → image_agent         hero image (real model via API key, else procedural fallback)
  → Compositor          assemble layers into pixels (deterministic)
  → BrandGuardian + Critic   QC: hard rules (veto) + taste score
  → Figma handoff       editable layers for final retouch
```
Multi-agent: each role is a specialized agent that reads/writes the shared **ad-spec**
(`Ad-Spec-Schema.md`, v0.2). See `Agent-Architecture.md`.

## Code map (root)
- `generation_pipeline.py` — the multi-agent generator + Orchestrator. **Main entry.**
- `product_discovery.py` — retrieves a product by interest (web-sourced list; swap for catalog matcher).
- `llm_agent.py` — Art Director / Copywriter brains (OpenAI/Anthropic, else data-driven fallback).
- `image_agent.py` — image-model adapter (OpenAI gpt-image-1 / Replicate Flux / procedural fallback).
- `ad_brief.py` — brand image STYLE + optional manual prompt/copy overrides.
- `baseline_render.py` — standalone premium "product-hero" poster renderer (the design baseline).
- `make_product_png.py` — renders a transparent product cutout → `product.png`.
- `spike_segmentation_matching.py` (in `Starbucks/`) — segmentation + matching validation spike.
- `figma-plugin/` — Figma dev plugin: ad-spec → editable layers.

## Design docs (read for intent, not code)
`Project-AD-Planning.md` (master plan), `Ad-Spec-Schema.md` (the contract),
`Agent-Architecture.md`, `Personalization-Design-System.md`,
`Product-Matching-and-Recommendation.md`, `Audience-Segmentation-and-Scaling.md`,
`Ad-Design-Language.md`, `Figma-Handoff.md`, `Brand-Identity-Template.md`.
Per-brand work lives in brand folders (`Starbucks/` is the worked example; `Nike/ Spotify/ Zara/` are stubs).

## Run
```bash
pip install -r requirements.txt
python3 make_product_png.py        # -> product.png (transparent cutout)
python3 baseline_render.py         # -> sbux_psl_ad.png (the poster baseline)
python3 generation_pipeline.py     # full agent run -> sbux_psl_ad.png + .spec.json
python3 Starbucks/spike_segmentation_matching.py   # segmentation/matching spike
```
Real models (optional): `export OPENAI_API_KEY=...` (image + LLM) or `REPLICATE_API_TOKEN` / `ANTHROPIC_API_KEY`.

## Conventions & current state (important)
- **Stand-in pattern:** where an external service isn't wired (LLM, embeddings, image model),
  code uses a deterministic, *data-driven* fallback — never a frozen hardcoded result.
  Real backends drop in behind the same interface (adapters in `*_agent.py` / `product_discovery.py`).
- **Nothing is hardcoded that should be generated:** the product is retrieved, the prompt & copy
  are generated from the segment + product data. Keep it that way.
- **Brand hard-rules are deterministic** (colors/fonts/logo/legal) and enforced by `BrandGuardian`;
  soft guidance is for the LLM. Don't let the model invent hex codes or fonts.
- **The ad-spec is the handoff contract** between agents — agents write only their own fields.
- Fonts/imagery/logo here are tasteful **stand-ins**; real brand fonts go in `fonts/`, real product
  cutout in `product.png`, real logo in `fonts/logo.png`.

## Good next tasks
- Swap `product_discovery.discover_candidates()` to the embedding catalog matcher from the spike.
- Wire a real LLM (`llm_agent`) + image model (`image_agent`) via keys and regenerate.
- Route the spike's real segments into `generation_pipeline` (end-to-end from clustered audience).
- Add unit tests for the QC gates and the spec validation rules.
