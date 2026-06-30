# Project AD

AI that designs **personalized, on-brand ads** (image / poster) for an audience segment —
retrieving the product, generating the imagery prompt and copy from data, compositing a
finished ad, QC-ing it against brand rules, and handing off to Figma for final retouch.

> New here? Read `CLAUDE.md` for the full architecture and code map, and
> `Project-AD-Planning.md` for the product plan.

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt

python3 make_product_png.py        # render a transparent product cutout -> product.png
python3 baseline_render.py         # render the poster baseline -> sbux_psl_ad.png
python3 generation_pipeline.py     # full multi-agent run -> ad + .spec.json
```

## Optional: real AI models
```bash
cp .env.example .env               # then add a key
export OPENAI_API_KEY=sk-...        # images (gpt-image-1) + LLM agents
# or REPLICATE_API_TOKEN (Flux images) / ANTHROPIC_API_KEY (Claude LLM)
```
Without a key, the pipeline runs end-to-end using deterministic, data-driven fallbacks.

## What's real vs. stand-in
Real: layout/typography, compositing, brand QC gates, the ad-spec contract, product
retrieval-by-interest, prompt/copy generation from data.
Stand-in (drop-in replaceable): LLM & image models (need keys), embeddings (keyword overlap
→ catalog matcher), brand fonts (`fonts/`), product photo (`product.png`), logo (`fonts/logo.png`).

## Layout
- Code: `generation_pipeline.py`, `product_discovery.py`, `llm_agent.py`, `image_agent.py`,
  `ad_brief.py`, `baseline_render.py`, `make_product_png.py`.
- Figma handoff: `figma-plugin/`.
- Design docs: the `*.md` files at root.
- Brands: `Starbucks/` (worked example), `Nike/ Spotify/ Zara/` (stubs).
