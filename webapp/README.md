# Project AD — Web console

A minimal Flask app that wraps the generator as a **project**-based tool.

## Features (v1)
- **Add project** — enter brand data (name, colors, identity, agenda, products,
  target audience interest), upload a logo, an optional transparent product
  cutout, and reference/past ads. On submit it generates a personalized minimal
  poster in the brand's color, aligned to the target interest.
- **View past projects** — a gallery of every project; click in for the poster,
  the project data, the reference ads, and a **Regenerate** button (each click
  produces a new diverse design from a new seed).

## Run
```bash
pip install -r requirements.txt      # includes flask
python3 webapp/app.py                 # -> http://localhost:5000
```

## Deploy (so you and others can use it via a URL)
The repo ships a `Procfile` (`web: gunicorn wsgi:app`) and a `wsgi.py` entry.

**Render (free, easiest):**
1. Push the repo to GitHub (done).
2. On https://render.com → New → Web Service → connect the repo/branch.
3. Build command: `pip install -r requirements.txt` · Start command: `gunicorn wsgi:app`.
4. Deploy → you get a public `https://<name>.onrender.com` URL to share.

**Railway / Fly.io / any host** work the same way via the `Procfile`.

Run it like production locally:
```bash
gunicorn wsgi:app            # -> http://localhost:8000
```
Note: the free tiers use an **ephemeral disk**, so `projects.db` and uploads
reset on redeploy. For durable storage, attach a persistent volume or swap
SQLite for a hosted Postgres + object storage (next step).

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
