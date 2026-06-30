# Ad-Spec Schema

*The contract between the art-director LLM and the renderer. The art-director **emits** an ad spec; the renderer **consumes** it to composite the final ad; the QC system **validates** against it. It is the most important artifact in Project AD — design it deliberately and version it strictly.*

Schema version: `0.2 (draft)` · Format: JSON · *Supersedes v0.1 — see Changelog at end.*

> **v0.2 in one line:** ads are generated **per audience segment**, not per user (see `Audience-Segmentation-and-Scaling.md`). A spec targets a `segment_id`; its `personalization` describes the segment representative, not an individual.

---

## Design goals

1. **Model-agnostic & renderer-agnostic** — describes *what the ad is*, not how any one tool makes it. Swappable image/LLM backends; same spec.
2. **Output-type-generic** — one schema spans static image, poster, and video. Output type is a field, not a fork. Video adds `timeline`; everything else is shared.
3. **Deterministic where it matters** — type, color, layout, logos, legal copy are explicit values the renderer places exactly. The model never "freehands" these.
4. **Generative only where intended** — imagery is described by a prompt + constraints; text/logos are never generated into the image.
5. **Reproducible & auditable** — same spec + same seeds → same ad. Every field is logged; human edits diff cleanly against the model's original.
6. **Validatable** — the QC system can check a render against the spec field-by-field.

---

## Top-level structure

```json
{
  "spec_version": "0.2",
  "ad_id": "uuid",
  "brand_id": "acme-coffee",
  "brand_config_version": 1,
  "segment_id": "seg_xxx",               // NEW v0.2 — the audience segment this ad serves
  "output": { "...": "format & dimensions" },
  "mode": "layered",
  "concept": { "...": "the creative idea" },
  "canvas": { "...": "background & imagery layers" },
  "elements": [ "...ordered visual elements: text, logo, image, shape, legal" ],
  "timeline": { "...": "video only — optional" },
  "personalization": { "...": "the SEGMENT representative this ad was built for" },
  "provenance": { "...": "models, seeds, prompts, who/what produced it" },
  "qc": { "...": "checks to run & their results" }
}
```

---

## Field reference

### Header
| Field | Type | Notes |
|---|---|---|
| `spec_version` | string | Schema version. Strict semver; renderer rejects unknown majors. |
| `ad_id` | uuid | Stable identity of this ad across regenerations/edits. |
| `brand_id` | string | Links to the brand-identity package. |
| `brand_config_version` | int | Pins which config version this ad was built against. |
| `segment_id` | string | **(v0.2)** The audience segment this ad is generated for and distributed to. One ad serves all members of the segment. |

### `output`
```json
"output": {
  "type": "image",              // "image" | "poster" | "video"
  "width": 1080,
  "height": 1350,
  "aspect_ratio": "4:5",
  "dpi": 144,                    // print posters need 300
  "format": "png",              // png | jpg | svg | mp4
  "duration_s": null,           // video only
  "fps": null                   // video only
}
```

### `mode`
`"layered"` *(default, client-facing)* or `"full_ai"` *(imagery-dominant, minimal text)*. Chosen by the art-director; recorded so QC applies the right ruleset.

### `concept`
The creative idea, in the model's words — used for review, critique scoring, and regeneration context.
```json
"concept": {
  "big_idea": "A quiet morning ritual, just for them.",
  "rationale": "Customer buys single-origin beans monthly and browses at 6–7am.",
  "copy_angle": "calm, personal, unhurried",
  "messaging_pillar": "craft"
}
```

### `canvas`
The generative imagery layer(s) and base background.
```json
"canvas": {
  "background": { "type": "color", "value": "#F5EFE2" },
  "imagery": [
    {
      "id": "img_hero",
      "role": "hero",
      "prompt": "overhead pour-over on a worn oak table, warm morning light...",
      "negative_prompt": "text, logos, watermark, extra fingers",
      "style_ref": "brand:imagery.style",
      "model_hint": "flux-pro",          // adapter resolves actual model
      "seed": 482193,
      "aspect_ratio": "4:5",
      "placement": { "x": 0, "y": 0, "w": 1080, "h": 900 },
      "post": { "grade": "brand:imagery.color_grade", "blur": 0 }
    }
  ]
}
```
> Imagery prompts are **constrained by the brand config** (`imagery.banned_subjects`, `must_avoid`, `style`). The renderer passes `negative_prompt` to block in-image text/logos. `seed` makes the imagery reproducible.
>
> **(v0.2)** `seed` is a **validated non-negative integer** — the schema rejects non-integer/garbled seeds at parse time (a real failure caught in the Starbucks spike). Omit the field for a random seed rather than passing a placeholder.

### `elements[]`
Ordered, z-indexed deterministic layers composited **on top of** imagery. The renderer places these exactly; the model only specifies content and intent, not pixels it shouldn't control.

Each element shares a base, plus a `type`-specific payload:
```json
{
  "id": "el_headline",
  "type": "text",                 // text | logo | image | shape | legal
  "z": 10,
  "box": { "x": 80, "y": 940, "w": 920, "h": 180, "anchor": "top-left" },
  "visibility": { "from_s": 0, "to_s": null }   // video timing; null = always
}
```

**`type: "text"`**
```json
{
  "type": "text",
  "content": "Your morning, considered.",
  "role": "headline",             // headline | subhead | body | cta
  "font": "brand:typography.fonts.heading",   // resolved from config — not freely chosen
  "size_px": 64,
  "weight": 600,
  "color": "brand:colors.primary",            // reference, validated against config
  "align": "left",
  "case": "sentence",
  "max_lines": 2,
  "autosize": { "min_px": 40, "max_px": 72 },  // shrink-to-fit within box
  "auto_scrim": true,             // (v0.2) renderer may inject a contrast scrim behind this text to pass the AA QC gate when it sits over imagery
  "copy": {
    "source": "generated",        // "manual" | "generated"
    "author": "system",           // "system" | user id, set when manual
    "locked": false,              // manual copy is locked → never reworded
    "brief": null,                // optional human direction the model writes to
    "brand_checked": "pass"       // brand-language QC result (set by QC, not author)
  }
}
```
> Fonts and colors are **references into the brand config**, not literals the model invents. QC rejects any literal that isn't in the config.

#### Copy authoring (manual vs. generated)
Copy is authored **per text element**, so a person can hand-write some lines and let the system write the rest of the same ad.

- **`source: "manual"`** — the person wrote `content`. The art-director **must not reword it**; `locked: true`. The renderer may still *fit* it (autosize, line-break) but never change the words.
- **`source: "generated"`** — the art-director writes `content` from the brand RAG (voice, pillars, do's/don'ts) + the selected product + audience angle. This is the default when the person provides nothing.
- **`brief`** — optional middle ground: the person gives direction ("lead with the seasonal angle, keep it under 6 words") and the model writes to it. `source` stays `"generated"` but the brief constrains it.
- **Brand check always runs, on both.** Manual and generated copy are both validated against `brand:language` (banned words, banned claims, reading grade, length/fit). Generated copy that fails is regenerated; **manual copy that fails is flagged for the human reviewer, never silently edited** — the person's words are respected, but they're told if a line breaks a brand rule.
- **Mixed ads are normal:** e.g. person writes the `headline` (manual, locked), the system generates `subhead` and `cta` (generated) so they stay consistent with the chosen product and the manual headline.

Resolution order per element: **manual content (locked) → brief-guided generation → free generation**. The art-director reads any manual/brief inputs first and writes only the unspecified elements, keeping the whole ad coherent.

**`type: "logo"`**
```json
{ "type": "logo", "variant": "mono-light", "box": {"...":"..."}, "respect_clear_space": true }
```
Pulled from the asset library; the renderer enforces `min_width_px`, `clear_space`, allowed placement, and the `do_not` rules. The model may pick *variant* and *allowed placement* only.

**`type: "legal"`** *(v0.2 — conditional resolution)*
```json
{
  "type": "legal",
  "content_ref": "brand:mandatory_copy.legal_line",          // dot-path into config
  "when_trigger": "rewards_offer",   // (v0.2) optional — include only if this trigger is active
  "size_px": 12
}
```
Always sourced from config; presence required if `layout.required_elements` includes it. `content_ref` is a **dot-path** resolved against the brand config (e.g. `brand:mandatory_copy.legal_line`, or a keyed disclaimer `brand:mandatory_copy.disclaimers[rewards_offer].text`). When `when_trigger` is set, the element is rendered **only if** that trigger condition is true for this ad (e.g. a price is shown, a rewards offer is present) — this resolves the v0.1 gap where disclaimers are an array keyed by trigger.

**`type: "shape"`** *(v0.2 — full payload)*
```json
{
  "type": "shape",
  "shape": "rect",                  // rect | line | rounded_rect
  "fill": "brand:colors.primary",   // config reference OR a gradient (below); no raw literals
  "opacity": 0.6,                   // 0–1
  "gradient": {                     // optional — overrides flat fill
    "type": "linear", "angle": 180,
    "stops": [
      { "color": "brand:colors.primary", "opacity": 0.0, "at": 0 },
      { "color": "brand:colors.primary", "opacity": 0.75, "at": 1 }
    ]
  },
  "radius_px": 0,
  "box": { "x": 0, "y": 700, "w": 1080, "h": 350, "anchor": "top-left" }
}
```
Brand-colored rectangles, dividers, and **scrims** (e.g. a gradient scrim behind text for contrast — the common case). All colors are config references; opacity and gradient stops let the renderer build a contrast scrim without a raw color literal. This resolves the v0.1 under-specified shape payload found in the Starbucks spike.

**`type: "image"`** — a fixed asset (not generative): product cutout, badge, QR. From the asset library.

### `timeline` *(video only)*
The same elements/imagery, animated. Static specs omit this entirely — that's how one schema covers all outputs.
```json
"timeline": {
  "duration_s": 8,
  "tracks": [
    { "element_id": "img_hero", "keyframes": [
      {"t": 0, "scale": 1.0}, {"t": 8, "scale": 1.08}     // slow push-in
    ]},
    { "element_id": "el_headline", "keyframes": [
      {"t": 1.0, "opacity": 0}, {"t": 1.6, "opacity": 1}  // fade up
    ]}
  ],
  "audio": { "track_ref": "brand:audio.default", "duck_under_vo": false }
}
```

### `personalization` *(v0.2 — segment-level)*
Describes the **audience segment** this ad was built for (not an individual) — for transparency, QC, and the feedback loop. The signals are the segment's *representative* (centroid/modal) traits, sourced from `Audience-Segmentation-and-Scaling.md`.
```json
"personalization": {
  "segment_id": "seg_sbux_fall_am_loyal",
  "segment_size": 14820,                   // (v0.2) how many users this one ad serves
  "signals_used": ["interest:fall_seasonal", "behavioral:morning_espresso", "lifecycle:loyal"],
  "inference": "loyal AM regulars receptive to a seasonal upgrade of their ritual",
  "selected_product": "sbux-psl-grande",   // (v0.2) chosen by product-matching + art-director
  "selection_reason": "highest lifecycle + interest fit; central seasonal hero",
  "literalness": "inferential",            // literal | inferential — segment ads skew inferential
  "pii_used": false,
  "off_limits_respected": true
}
```
> Because one ad serves a whole segment, `literalness` is **almost always `"inferential"`** — a grouped ad can't reference one person's saved item. Literal personalization is reserved for segments so tight that a literal line is true for every member, in an owned channel.

### `provenance`
```json
"provenance": {
  "art_director_model": "claude-x",
  "image_models": [{"id": "img_hero", "model": "flux-pro", "seed": 482193}],
  "created_by": "system",                  // system | human_edit
  "parent_ad_id": null,                    // set when regenerated/edited
  "created_at": "2026-06-30T09:00:00Z"
}
```

### `qc`
Checks to run and their results — written by the QC system, not the model.
```json
"qc": {
  "gates": {
    "color_in_tolerance": "pass",
    "logo_integrity": "pass",
    "text_legible": "pass",
    "contrast_aa": "pass",
    "safe_zone": "pass",
    "legal_present": "pass",
    "resolution_correct": "pass"
  },
  "ai_critique": { "score": 0.86, "verdict": "approve", "notes": "strong hierarchy; warm grade on-brand" },
  "human": { "decision": null, "reviewer": null, "edits": [] }
}
```

---

## Worked example (minimal static ad)

```json
{
  "spec_version": "0.1",
  "ad_id": "9f1c-...",
  "brand_id": "acme-coffee",
  "brand_config_version": 1,
  "output": { "type": "image", "width": 1080, "height": 1350, "aspect_ratio": "4:5", "format": "png" },
  "mode": "layered",
  "concept": { "big_idea": "A quiet morning ritual, just for them.", "messaging_pillar": "craft" },
  "canvas": {
    "background": { "type": "color", "value": "brand:colors.secondary" },
    "imagery": [{ "id": "img_hero", "role": "hero",
      "prompt": "overhead pour-over on worn oak, warm morning light, film grain",
      "negative_prompt": "text, logos, watermark", "seed": 482193,
      "placement": { "x": 0, "y": 0, "w": 1080, "h": 900 } }]
  },
  "elements": [
    { "id": "el_head", "type": "text", "z": 10, "role": "headline",
      "content": "Your morning, considered.",
      "font": "brand:typography.fonts.heading", "size_px": 64, "color": "brand:colors.primary",
      "box": { "x": 80, "y": 950, "w": 920, "h": 160, "anchor": "top-left" } },
    { "id": "el_logo", "type": "logo", "z": 20, "variant": "mono-dark",
      "box": { "x": 80, "y": 1180, "w": 160, "h": 48 } },
    { "id": "el_legal", "type": "legal", "z": 20,
      "content_ref": "brand:mandatory_copy.legal_line", "size_px": 12,
      "box": { "x": 80, "y": 1290, "w": 920, "h": 24 } }
  ],
  "segment_id": "seg_demo",
  "personalization": { "segment_id": "seg_demo", "segment_size": 14820, "signals_used": ["purchase_history:single_origin"], "literalness": "inferential", "pii_used": false },
  "provenance": { "art_director_model": "claude-x", "created_by": "system", "parent_ad_id": null }
}
```

---

## Validation rules (enforced before render)
1. `font` / `color` references must resolve to entries in the pinned brand config — **no literals** the config doesn't contain.
2. All `layout.required_elements` must be present as elements.
3. Every imagery `negative_prompt` must include the brand's `imagery.must_avoid` (text, logos).
4. Element `box`es must sit inside the `safe_margin_pct`; logos must honor `clear_space`.
5. `output.type == "video"` requires a `timeline`; non-video must omit it.
6. `mode == "layered"` requires at least one `text` or `logo` element rendered deterministically.
7. `copy.source == "manual"` ⇒ `locked: true`; the art-director must not alter `content`. All copy (manual or generated) must pass `brand:language` checks; generated failures regenerate, manual failures flag for human review.
8. **(v0.2)** `segment_id` is required; the ad is generated once and served to all members of that segment.
9. **(v0.2)** `seed` must be a non-negative integer when present.
10. **(v0.2)** `shape.fill` / `gradient.stops[].color` must be config references, not raw literals.
11. **(v0.2)** a `legal` element with `when_trigger` renders only when that trigger is active.

---

## Changelog

**v0.2** (current)
- **Segment-level generation** — added top-level `segment_id`; `personalization` now describes the segment representative + `segment_size` + chosen product, not an individual. One ad serves a whole cohort. (See `Audience-Segmentation-and-Scaling.md`.)
- **Copy authoring** — per-element `copy` block: `source` (manual/generated), `locked`, `author`, `brief`, `brand_checked`. Manual copy is never reworded; both manual and generated copy pass brand-language checks.
- **Spike fix 1 — shape payload** — full `shape` spec with `fill`, `opacity`, `gradient.stops`, `radius_px` (enables contrast scrims).
- **Spike fix 2 — conditional legal** — `content_ref` dot-path resolution + `when_trigger` for trigger-keyed disclaimers.
- **Spike fix 3 — `auto_scrim`** on text elements so the renderer can guarantee AA contrast over imagery.
- **Spike fix 4 — seed validation** — `seed` constrained to a non-negative integer.

**v0.1** — initial draft: model/renderer-agnostic layered spec; output-type-generic (image/poster/video via `timeline`); deterministic type/layout/logo/legal; generative imagery only; reproducible & validatable.

---

## Notes for the design spike
- Validate this schema against **3–4 real target ads** by hand-authoring their specs before building the renderer. If a real ad can't be expressed, the schema is wrong — fix it now, not after the renderer exists.
- Decide reference-resolution syntax (`brand:...`) and lock it; it's load-bearing across model, renderer, and QC.
- Keep `spec_version` discipline from day one — the renderer, art-director prompt, and QC all key off it.
