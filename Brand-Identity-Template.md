# Brand-Identity Package — Template

*One package per brand. Two parts: (A) a structured **config** of hard constraints the renderer enforces, and (B) prose **guidance** documents the art-director LLM retrieves via RAG. Copy this file per brand, fill every field, leave nothing blank — use "N/A" with a reason if truly not applicable.*

Brand: `____________`  ·  Package version: `v1`  ·  Owner: `____________`  ·  Last updated: `____________`

---

# PART A — Brand Config (hard constraints)

> Machine-read and **enforced deterministically**. These are facts, not suggestions. Store as `brand-config.yaml` alongside this doc. Values below are the schema with example placeholders.

```yaml
brand_id: acme-coffee            # stable slug, never reused
display_name: "Acme Coffee Co."
version: 1

# --- Color ---
colors:
  primary:   { name: "Acme Green",  hex: "#1A3C2B", tolerance_deltaE: 3 }
  secondary: { name: "Cream",       hex: "#F5EFE2", tolerance_deltaE: 3 }
  accents:
    - { name: "Copper", hex: "#B06A3C" }
  neutrals:
    - { name: "Ink",    hex: "#14110F" }
    - { name: "Paper",  hex: "#FFFFFF" }
  banned_colors: ["#FF0000"]        # colors never to appear
  background_rules: "Primary or Cream only; never accent as full-bleed background."

# --- Typography ---
typography:
  fonts:
    heading: { family: "Canela",  weights: [400, 600], source_file: "fonts/Canela.otf" }
    body:    { family: "Inter",   weights: [400, 500], source_file: "fonts/Inter.ttf" }
  fallback_stack: ["Georgia", "serif"]
  min_body_size_px: 14
  case_rules: "Headlines: sentence case. Never ALL CAPS for body."
  tracking_rules: "Headlines -2%; body 0."
  banned_fonts: ["Comic Sans", "system default sans for headings"]

# --- Logo & marks ---
logo:
  primary_file: "assets/logo-primary.svg"
  variants:
    - { name: "mono-light", file: "assets/logo-mono-light.svg", use: "on dark bg" }
    - { name: "mono-dark",  file: "assets/logo-mono-dark.svg",  use: "on light bg" }
  min_width_px: 96
  clear_space: "0.5x logo height on all sides"   # exclusion zone
  placement_allowed: ["top-left", "bottom-center"]
  do_not: ["recolor", "rotate", "stretch", "add effects", "place on busy imagery"]

# --- Layout & safe zones ---
layout:
  safe_margin_pct: 6              # keep critical content inside this margin
  grid: "12-col, 24px gutter"
  logo_safe_zone: true
  required_elements: ["logo", "legal_line"]   # must appear on every ad

# --- Mandatory copy ---
mandatory_copy:
  legal_line: "© Acme Coffee Co. All rights reserved."
  disclaimers:
    - { trigger: "price_shown", text: "Prices may vary by region." }
  required_hashtags: ["#AcmeCoffee"]

# --- Language constraints ---
language:
  banned_words: ["cheap", "discount", "guru"]
  banned_claims: ["best in the world", "#1"]   # legal/positioning risk
  reading_grade_max: 8
  approved_tone_words: ["warm", "crafted", "considered"]

# --- Imagery constraints (guides the generative model) ---
imagery:
  allowed_subjects: ["coffee, hands, cafe interiors, daylight scenes"]
  banned_subjects: ["alcohol", "competitor products", "stock-photo clichés"]
  style: "natural light, warm grade, shallow depth of field, film grain"
  must_avoid: ["text rendered in image", "logos rendered in image", "extra fingers"]
  color_grade: "warm, low-contrast, slightly desaturated"
  aspect_ratios: ["1:1", "4:5", "9:16", "16:9"]

# --- Accessibility ---
accessibility:
  min_contrast_ratio: 4.5         # WCAG AA for text
  min_text_size_px: 14
```

---

# PART B — Brand Guidance (soft, for RAG)

> Prose. Chunked, embedded, and **retrieved** to inform concept and copy. Write naturally and specifically — the *why* matters more than the *what*. Each section below becomes one or more retrievable documents.

## B1. Brand essence
*One paragraph: what this brand fundamentally is and stands for. The single sentence a stranger should walk away with.*

## B2. Personality & voice
*If the brand were a person, who are they? List 3–5 traits with a sentence each. Then: how do they speak? Provide 2–3 "we say this / not that" pairs.*

- We sound: `____`
- We never sound: `____`
- Say this: "`____`"  ·  Not that: "`____`"

## B3. Audience & their interests
*Who are we talking to? What do they care about, aspire to, fear? What makes them lean in vs. scroll past? This is where personalization hooks attach.*

## B4. Mood & visual feeling
*Describe the emotional register of the visuals in words (not specs — specs live in Part A). "Quiet morning light, unhurried, tactile." Reference textures, times of day, feelings.*

## B5. Do's and don'ts (with reasons)
*The judgment calls a config can't encode. Each item gets a reason.*

- DO: `____` — because `____`
- DON'T: `____` — because `____`

## B6. Exemplar campaigns
*2–4 examples of past or aspirational ads that nail the brand, each with a short note on **why** it works. These are the strongest retrieval anchors — be concrete.*

## B7. Anti-examples
*Ads (yours or competitors') that feel off-brand, and why. Equally valuable for steering the model away.*

## B8. Messaging pillars
*The 3–4 core ideas every campaign should ladder up to. For each: the idea, and the proof behind it.*

## B9. Personalization guidance
*How should customer data shape the ad without feeling creepy or generic? What signals are fair game (interests, past purchases, season, location)? What's off-limits? How literal vs. inferential should personalization be?*

---

## Authoring checklist
- [ ] Every Part A field filled (no silent blanks)
- [ ] All asset files present at referenced paths (fonts, logos, etc.)
- [ ] Hex codes verified against brand source-of-truth
- [ ] Part B sections written specifically, not generically
- [ ] At least 2 exemplars and 1 anti-example provided
- [ ] Reviewed by the embedded designer before first generation
