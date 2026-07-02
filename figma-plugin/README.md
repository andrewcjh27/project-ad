# Project AD — Figma Ad Importer (plugin)

Turns a generated ad-spec + its hero image into **editable Figma layers** so a designer can do final retouch. Implements the one-way handoff from `Figma-Handoff.md`.

## Files
- `manifest.json` — plugin manifest (no network access; inputs come through the UI).
- `code.js` — main: maps ad-spec → Figma nodes (frame, image fill, text, scrim, logo).
- `ui.html` — paste spec JSON + pick the hero PNG.

## Install (development plugin)
1. In the Figma **desktop** app: menu → **Plugins → Development → Import plugin from manifest…**
2. Select `figma-plugin/manifest.json`.
3. Run it from **Plugins → Development → Project AD — Ad Importer**.

## Use — from the Ad Studio (recommended)
1. In the **Ad Studio** (`ad-studio.html`): generate an ad, then click **Export spec** (downloads `<brand>.spec.json`) and **Download** (the PNG).
2. Open the plugin, **paste the `.spec.json`** into the JSON box.
3. **Choose the downloaded PNG** as the hero image (for full-AI ads this is the whole ad; for layered ads it's the composed poster).
4. Click **Build in Figma** — an editable frame appears:
   - headline / subhead → real **TextNodes** at their spec `box` (reword, restyle freely; `size_px`/`color` honored)
   - hero → image fill (swap/replace/mask)
   - shapes/scrims → rectangles; logo → placeholder ellipse

The studio exports **raw hex** colors and per-element `size_px`/`box`; `code.js`'s `resolveColor` now reads raw hex directly, so the studio's spec builds without a brand palette. (Alternatively, run the Python pipeline for `brand:`-referenced specs.)

## Use — from the Python pipeline
1. Run `generation_pipeline.py` to get `*.spec.json` + the hero PNG.
2. Paste the spec, choose the PNG, **Build in Figma**.

## Production notes
- **Fonts:** the plugin defaults to Inter so it never fails on a missing font. Upload your brand fonts (e.g. Starbucks Sodo Sans / Lander / Pike) to your Figma org and switch `fontFor()` in `code.js` to use them.
- **Logo:** replace the placeholder ellipse with an instance of your brand's shared **logo component** (preserves integrity + clear-space).
- **Colors:** `PALETTES` in `code.js` is a per-brand color map; load it from the brand package keyed by `brand_id`, ideally as Figma color **variables/styles** so designer edits stay on-palette.
- **Manual copy:** text elements whose spec `copy.source == "manual"` are name-tagged `· MANUAL (locked)` so designers know not to reword them.
- **Flow is one-way** (spec → Figma → export) for v1; designer edits are not synced back to the spec.
