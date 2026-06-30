# Ad Design Language — from reference set

*Extracted from four reference ads supplied by Junho (Apple "Beyond Innovation", Alure Skin Care, Starbucks "The Royal Coffee", 2% near-water). This is the visual template the renderer targets — encoded in `baseline_render.py`.*

---

## Shared DNA (the rules all four obey)

1. **Product is the hero.** Large, central or dynamically angled, the clear focal point. Everything else serves it.
2. **Dramatic, brand-colored background with depth.** Not flat — a graded field with a glow behind the product and a vignette at the edges (eclipse black, organic green, royal red, fresh blue).
3. **Physicality & context.** Reflections, contact shadows, splashes, floating ingredients — the product sits in a believable space.
4. **Confident typography, sparse words.** A display/script headline + a short subhead. Minimal body copy. Often a huge translucent **watermark** word (Alure "ALURE", the "2%").
5. **Framing & marks.** Thin border frames, anchored logo, footer emblem/tagline ("SINCE 1971").
6. **Premium restraint.** Generous negative space; nothing competes with the product.

## Per-reference notes
| Reference | Background | Product treatment | Type | Signature move |
|---|---|---|---|---|
| Apple | Eclipse black, rim light | Emerging from shadow, lower-right | Centered headline + thin subhead, logo top | Negative space + mystery |
| Alure | Organic green waves | Floating tube + ingredients | Logo top-right, body bottom-right | Giant translucent "ALURE" watermark |
| Starbucks Royal | Royal red, center glow | Centered cup + splash + floor reflection | Script headline, "SINCE 1971" footer | Thin frame + footer emblem |
| 2% Water | Bright blue water | Two bottles + fruit + ripples | Huge "2%" + supporting copy | Product-as-typography scale |

---

## Encoded template (current baseline)

`baseline_render.py` implements the **premium product-hero** template, tuned to the Starbucks Royal reference:

- `dramatic_background()` — graded brand field + warm core glow + vignette + grain.
- `place_product()` — inserts a transparent product PNG, scaled, with **reflection** + contact shadow.
- thin **frame**, centered **display headline + subhead**, **footer emblem + tagline with side rules**.
- optional big **watermark** word (`COPY["watermark"]`) for the Alure/2% style.

All knobs live in the `DESIGN` block: `C` (palette), `COPY`, `TYPE`, frame inset, product size/position, reflection on/off.

## To reach full reference fidelity (asset checklist)
- [ ] **Real product cutout** → `product.png` (transparent). Biggest single upgrade.
- [ ] **Brand fonts** → `fonts/display.ttf` (a script for "Starbucks"), `label.ttf`, `body.ttf`.
- [ ] **Real logo** → `fonts/logo.png` (the Siren) for the footer/header.
- [ ] **Photographic background or splash** → needs a real/generated image (image-model key); the graded field is the stand-in until then.

## Style presets to build next (one per reference vibe)
- `royal` (current) — dark dramatic, centered, framed, footer emblem.
- `organic` — light, flowing, floating product + ingredients + big watermark (Alure).
- `mystery` — near-black, rim-lit, off-center product, max negative space (Apple).
- `fresh` — bright, product-as-typography scale, multiple products (2% water).

Each preset is just a different `DESIGN` block + a couple of layout flags over the same engine.
