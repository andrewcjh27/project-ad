# Starbucks — Sample Ad Specs (Design Spike)

*Three hand-authored ad specs against `Ad-Spec-Schema.md`, using the `Starbucks-Brand-Package.md`. Purpose: validate that the schema + rulebook can express real, differentiated, personalized ads before any renderer is built. Each spec is followed by **which rules fired** (traceability) and notes.*

---

## Scenario A — Loyal AM regular → seasonal drink

**Audience:** Rewards member, buys a latte most weekday mornings, high frequency, recent. **Product:** Pumpkin Spice Latte (seasonal launch). **Channel:** app/email (owned → literal personalization allowed).

```json
{
  "spec_version": "0.1",
  "ad_id": "sbux-a-0001",
  "brand_id": "starbucks",
  "brand_config_version": 1,
  "output": { "type": "image", "width": 1080, "height": 1350, "aspect_ratio": "4:5", "format": "png" },
  "mode": "layered",
  "concept": {
    "big_idea": "Your morning just got its season back.",
    "rationale": "Daily AM latte regular; PSL season reframes their existing ritual as a seasonal treat.",
    "copy_angle": "warm, expressive, ritual-anchored",
    "messaging_pillar": "seasonal-moments"
  },
  "canvas": {
    "background": { "type": "color", "value": "brand:colors.accents.Warm Cream" },
    "imagery": [{
      "id": "img_hero", "role": "hero",
      "prompt": "a hand holding a warm PSL in a Starbucks-style cup on a wooden cafe table, autumn morning light, cinnamon and foam, shallow depth of field, cozy",
      "negative_prompt": "text, logos, watermark, extra fingers, misshapen cup",
      "style_ref": "brand:imagery.style", "seed": 771204,
      "placement": { "x": 0, "y": 0, "w": 1080, "h": 880 },
      "post": { "grade": "brand:imagery.color_grade" }
    }]
  },
  "elements": [
    { "id": "el_head", "type": "text", "z": 10, "role": "headline",
      "content": "Your morning, now in pumpkin spice.",
      "font": "brand:typography.fonts.expressive", "size_px": 60, "weight": 700,
      "color": "brand:colors.primary", "align": "left", "case": "sentence", "max_lines": 2,
      "box": { "x": 80, "y": 930, "w": 920, "h": 170, "anchor": "top-left" } },
    { "id": "el_sub", "type": "text", "z": 10, "role": "subhead",
      "content": "It's back — order ahead and skip the wait.",
      "font": "brand:typography.fonts.body", "size_px": 26, "weight": 400,
      "color": "brand:colors.secondary", "align": "left", "max_lines": 1,
      "box": { "x": 80, "y": 1110, "w": 920, "h": 40, "anchor": "top-left" } },
    { "id": "el_logo", "type": "logo", "z": 20, "variant": "siren-green",
      "box": { "x": 80, "y": 60, "w": 88, "h": 88 }, "respect_clear_space": true }
  ],
  "personalization": {
    "signals_used": ["rewards:daily_latte_am", "favorite:latte", "lifecycle:loyal", "season:fall"],
    "inference": "values the daily ritual; receptive to a seasonal upgrade of it",
    "literalness": "inferential",
    "pii_used": false,
    "off_limits_respected": true
  },
  "provenance": { "art_director_model": "claude-x", "created_by": "system", "parent_ad_id": null }
}
```

**Rules fired:** §5 Consumable+Experiences playbook (ritual + anticipation) · §4 Behavioral "high category affinity" → lead with their category · §4 Lifecycle "loyal" → minimal offer, premium framing (order-ahead convenience, no discount) · §4 Contextual "season" → seasonal product & mood. **Voice:** expressive tone (B2) for focal seasonal product. **Offer posture:** soft (convenience, not discount) — correct for loyal.

---

## Scenario B — Lapsed customer → win-back

**Audience:** Rewards member, no purchase in ~6 weeks (lapsed). **Product:** a "free favorite" Rewards re-activation, drink = their known favorite (Cold Brew). **Channel:** email/app.

```json
{
  "spec_version": "0.1",
  "ad_id": "sbux-b-0001",
  "brand_id": "starbucks",
  "brand_config_version": 1,
  "output": { "type": "image", "width": 1080, "height": 1350, "aspect_ratio": "4:5", "format": "png" },
  "mode": "layered",
  "concept": {
    "big_idea": "We saved your favorite a seat.",
    "rationale": "Lapsed regular; win-back via their own favorite + a Rewards gift, framed as belonging not discount.",
    "copy_angle": "warm, welcoming, light nudge",
    "messaging_pillar": "belonging"
  },
  "canvas": {
    "background": { "type": "color", "value": "brand:colors.primary" },
    "imagery": [{
      "id": "img_hero", "role": "hero",
      "prompt": "an iced cold brew in a clear cup on a bright cafe counter, condensation, fresh morning light, green and cream tones, inviting",
      "negative_prompt": "text, logos, watermark, extra fingers, misshapen cup",
      "style_ref": "brand:imagery.style", "seed": 339072,
      "placement": { "x": 0, "y": 250, "w": 1080, "h": 850 },
      "post": { "grade": "brand:imagery.color_grade" }
    }]
  },
  "elements": [
    { "id": "el_scrim", "type": "shape", "z": 5, "shape": "rect",
      "color": "brand:colors.primary", "opacity": 0.0,
      "box": { "x": 0, "y": 0, "w": 1080, "h": 250 } },
    { "id": "el_head", "type": "text", "z": 10, "role": "headline",
      "content": "Your Cold Brew misses you.",
      "font": "brand:typography.fonts.expressive", "size_px": 58, "weight": 700,
      "color": "brand:colors.accents.Warm Cream", "align": "left", "case": "sentence", "max_lines": 2,
      "box": { "x": 80, "y": 70, "w": 920, "h": 150, "anchor": "top-left" } },
    { "id": "el_cta", "type": "text", "z": 10, "role": "cta",
      "content": "Here's a free favorite, on us. Tap to redeem.",
      "font": "brand:typography.fonts.body", "size_px": 28, "weight": 700,
      "color": "brand:colors.accents.Warm Cream", "align": "left", "max_lines": 2,
      "box": { "x": 80, "y": 1140, "w": 920, "h": 90, "anchor": "top-left" } },
    { "id": "el_logo", "type": "logo", "z": 20, "variant": "siren-white",
      "box": { "x": 940, "y": 60, "w": 80, "h": 80 }, "respect_clear_space": true },
    { "id": "el_legal", "type": "legal", "z": 20,
      "content_ref": "brand:mandatory_copy.disclaimers.rewards_offer",
      "font": "brand:typography.fonts.body", "size_px": 14,
      "color": "brand:colors.accents.Warm Cream",
      "box": { "x": 80, "y": 1250, "w": 920, "h": 24, "anchor": "top-left" } }
  ],
  "personalization": {
    "signals_used": ["lifecycle:lapsed_6w", "favorite:cold_brew", "rewards:active_member"],
    "inference": "needs a warm reason to return; their own favorite is the strongest hook",
    "literalness": "literal",
    "pii_used": false,
    "off_limits_respected": true
  },
  "provenance": { "art_director_model": "claude-x", "created_by": "system", "parent_ad_id": null }
}
```

**Rules fired:** §4 Lifecycle "churning/lapsed" → win-back concept + strongest *permitted* offer (free favorite, framed as gift) · §4 Expressed "favorite" → product = their exact favorite, literal personalization OK (high confidence, owned channel) · §6 guardrail → "free favorite" framed via **belonging** pillar, avoiding banned words "discount/deal." **Legal:** rewards_offer disclaimer auto-included (config trigger). **Note:** literalness="literal" is licensed here because the favorite is high-confidence Rewards data in an owned channel.

---

## Scenario C — New customer → brand intro (no-data fallback)

**Audience:** First-time, no history (the no-data fallback path). **Product:** brand essence + current seasonal hero. **Channel:** paid social (inferential only).

```json
{
  "spec_version": "0.1",
  "ad_id": "sbux-c-0001",
  "brand_id": "starbucks",
  "brand_config_version": 1,
  "output": { "type": "image", "width": 1080, "height": 1920, "aspect_ratio": "9:16", "format": "png" },
  "mode": "layered",
  "concept": {
    "big_idea": "There's a seat here for you.",
    "rationale": "No data — sell the brand essence (the third place) + a warm seasonal hero, no offer.",
    "copy_angle": "warm, inviting, expressive",
    "messaging_pillar": "ritual-and-comfort"
  },
  "canvas": {
    "background": { "type": "color", "value": "brand:colors.accents.Warm Cream" },
    "imagery": [{
      "id": "img_hero", "role": "hero",
      "prompt": "two hands wrapped around a warm Starbucks-style cup at a sunlit cafe window, soft steam, cozy third-place atmosphere, green and cream palette, human and inviting",
      "negative_prompt": "text, logos, watermark, extra fingers, misshapen cup",
      "style_ref": "brand:imagery.style", "seed": 905512,
      "placement": { "x": 0, "y": 0, "w": 1080, "h": 1500 },
      "post": { "grade": "brand:imagery.color_grade" }
    }]
  },
  "elements": [
    { "id": "el_head", "type": "text", "z": 10, "role": "headline",
      "content": "Your third place is waiting.",
      "font": "brand:typography.fonts.expressive", "size_px": 64, "weight": 700,
      "color": "brand:colors.primary", "align": "left", "case": "sentence", "max_lines": 2,
      "box": { "x": 80, "y": 1560, "w": 920, "h": 180, "anchor": "top-left" } },
    { "id": "el_logo", "type": "logo", "z": 20, "variant": "siren-green",
      "box": { "x": 80, "y": 90, "w": 96, "h": 96 }, "respect_clear_space": true }
  ],
  "personalization": {
    "signals_used": [],
    "inference": "no data — brand-essence fallback",
    "literalness": "inferential",
    "pii_used": false,
    "off_limits_respected": true
  },
  "provenance": { "art_director_model": "claude-x", "created_by": "system", "parent_ad_id": null }
}
```

**Rules fired:** §6 "no-data fallback required" → brand essence + seasonal hero, no offer · §4 Lifecycle "new visitor" → brand-first, soft, high-polish hero · §3 zero signals → strictly inferential · §5 format: 9:16 chosen for paid-social story placement. **Voice:** expressive, belonging-adjacent. **Offer:** none — correct for cold first impression.

---

## Validation summary (did the schema hold?)

| Test | Result |
|---|---|
| Three visibly different ads from one brand package | ✅ Concept, product, format, offer, voice all differentiate per scenario. |
| Hard constraints stay as config references (`brand:...`) | ✅ All fonts/colors are references; no invented literals. |
| Personalization traceable to rules | ✅ Each spec lists which §4/§5/§6 rules fired. |
| Literal vs. inferential gated by confidence + channel | ✅ Literal only in B (owned + high-confidence); inferential in A and C. |
| No-data path produces an excellent ad | ✅ Scenario C. |
| Legal/disclaimer auto-inclusion via config trigger | ✅ Scenario B rewards disclaimer. |

**Schema gaps found (fix before renderer):**
1. **Shape element** needs a defined `opacity` + `gradient` payload — Scenario B wanted a scrim behind text on photo; the schema's `shape` type is under-specified. Add `fill`, `opacity`, `gradient{stops}` to the shape payload.
2. **Legal `content_ref` to a *conditional* disclaimer** (rewards_offer) needs a resolution rule — currently `content_ref` assumes a single string; disclaimers are an array keyed by trigger. Define `content_ref` dot-path resolution + a `when_trigger` field.
3. **Text-on-image contrast** isn't guaranteed by the spec alone (Scenario A headline sits over imagery edge). Add an optional `auto_scrim: true` on text elements that lets the renderer inject a contrast scrim to pass the AA QC gate.
4. One seed value was malformed during authoring — reinforces that **seeds must be schema-validated integers**; add a format constraint.

**Verdict:** the schema and rulebook express all three scenarios with real differentiation and full traceability. Four small schema refinements identified — exactly what the spike is for. Recommend folding fixes 1–4 into `Ad-Spec-Schema.md v0.2`, then build the Phase 0 static renderer against v0.2.
