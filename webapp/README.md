# Project AD — Web console

A minimal Flask app that wraps the generator as a **project**-based tool.

## Features (v1)
- **Add project** — a 3-step wizard: **Brief** (name, description, customer/
  audience data, product data), **Brand identity** (colors, brand values, voice,
  agenda, optional headline/subhead, logo), and **References** (optional past ads
  + product cutout). On submit it generates a personalized minimal poster.
- **AI by default** — with a Gemini key on the server the background and copy are
  AI-generated; without one (or on any API error) it falls back to a minimal
  procedural preset. Reference uploads steer the AI background's palette/mood.
- **View past projects** — a gallery of every project; click in for the poster,
  the project data, the reference ads, and a **Regenerate** button (each click
  produces a new diverse design from a new seed).

## Run
```bash
pip install -r requirements.txt      # includes flask
python3 webapp/app.py                 # -> http://localhost:5000
```

## Deploy (so you and others can use it via a URL)
The repo ships `wsgi.py` (entry), a `Procfile`, and a **`render.yaml` blueprint**.

**Render (free, easiest) — one-click blueprint:**
1. Push the repo to GitHub (done).
2. On https://render.com → **New → Blueprint** → connect the repo. Render reads
   `render.yaml` and provisions the web service automatically.
3. When prompted, paste your **Gemini keys** (they are `sync:false`, so they live
   only in Render, never in the repo):
   - `GEMINI_API_KEY` — free-tier key, powers AI copy (and images if the key is billed).
   - `GEMINI_IMAGE_API_KEY` — optional separate billed key for images; omit and
     images fall back to the preset.
   - `AD_IMAGE_PROVIDER` *(optional)* — set `procedural` to skip AI image calls
     entirely (useful while image quota is 0), or `gemini` to force them.
4. Deploy → you get a public `https://<name>.onrender.com` URL to share.

The blueprint deploys from **`master`** — merge your branch there first (or edit
`render.yaml`'s `branch:`). **Railway / Fly.io / any host** work the same way via
the `Procfile`.

Run it like production locally:
```bash
gunicorn wsgi:app --bind 0.0.0.0:8000      # -> http://localhost:8000
```
Note: free tiers use an **ephemeral disk**, so `projects.db` and uploads reset on
redeploy. For durable storage, attach a persistent volume or swap SQLite for a
hosted Postgres + object storage (next step).

## Storage (all local, gitignored)
- `webapp/projects.db` — SQLite, one row per project
- `webapp/uploads/<project_id>/` — uploaded logo / product / reference ads
- `webapp/generated/<project_id>.png` — the generated poster

## How it generates
`webapp/generator.py` reuses `image_agent.ProceduralProvider` for the diverse
minimal background (driven by the brand color), then composites the logo
(top-left), an optional product cutout (upper-center), and the headline/subhead
(dark text, lower third). Same minimal/diverse principles as the main pipeline.

## Next steps
- Wire the full multi-agent pipeline per project (brand-specific catalog,
  segmentation, brand memory) instead of the standalone generator.
- LLM-written headlines from the agenda/interest when an API key is set.
- The design is intentionally plain — restyle `webapp/static/style.css` later.
