# Brand-Identity Package — Starbucks (TEST BRAND)

*Instantiation of `Brand-Identity-Template.md` + `Personalization-Design-System.md` for Starbucks, as the first test brand. Brand facts sourced from Starbucks Creative Expression and public brand references (see Sources). Values are realistic for testing; confirm against official brand assets before any production use.*

Brand: **Starbucks** · Package version: `v1` · Owner: Junho · Last updated: 2026-06-30

---

# PART A — Brand Config (hard constraints)

```yaml
brand_id: starbucks
display_name: "Starbucks"
version: 1

# --- Color ---
colors:
  primary:   { name: "Starbucks Green", hex: "#00704A", pantone: "3425C", tolerance_deltaE: 2 }
  secondary: { name: "House Green (dark)", hex: "#006241", tolerance_deltaE: 2 }
  accents:
    - { name: "Accent Green (light)", hex: "#1E3932" }   # deep forest, for depth
    - { name: "Warm Cream",  hex: "#F2F0EB" }
  neutrals:
    - { name: "Black", hex: "#000000" }
    - { name: "White", hex: "#FFFFFF" }
  banned_colors: ["#FF0000", "competitor red"]   # avoid associations / non-brand reds
  background_rules: "White, Warm Cream, or Starbucks Green only for full-bleed. Never use accent greens as large flat backgrounds; reserve for depth/detail."

# --- Typography ---
typography:
  fonts:
    heading:    { family: "Pike",      weights: [600, 700], source_file: "fonts/Pike.otf",   use: "functional headlines, wayfinding, impactful condensed" }
    expressive: { family: "Lander",    weights: [400, 700], source_file: "fonts/Lander.otf", use: "serif accent for expressive, day-making moments" }
    body:       { family: "Sodo Sans", weights: [400, 500, 700], source_file: "fonts/SodoSans.ttf", use: "body, UI, most copy" }
  fallback_stack: ["Helvetica Neue", "Arial", "sans-serif"]
  min_body_size_px: 14
  case_rules: "Sentence case default. No ALL CAPS for body. Headlines may use title or sentence case."
  banned_fonts: ["Comic Sans", "default system serif for headlines"]

# --- Logo & marks ---
logo:
  primary_file: "assets/siren-green.svg"     # wordless Siren (current since 2011)
  variants:
    - { name: "siren-green",  file: "assets/siren-green.svg",  use: "on white/cream/light" }
    - { name: "siren-white",  file: "assets/siren-white.svg",  use: "on green/dark/photo" }
    - { name: "siren-black",  file: "assets/siren-black.svg",  use: "mono, light bg only" }
  min_width_px: 64
  clear_space: "0.5x Siren diameter on all sides"
  placement_allowed: ["top-left", "top-center", "bottom-center"]
  do_not: ["recolor outside approved variants", "rotate", "stretch", "add wordmark", "add drop shadow/effects", "place on busy imagery without scrim"]

# --- Layout & safe zones ---
layout:
  safe_margin_pct: 6
  grid: "12-col, 24px gutter"
  logo_safe_zone: true
  required_elements: ["logo"]                 # legal line only when required by channel/offer

# --- Mandatory copy ---
mandatory_copy:
  legal_line: "© 2026 Starbucks Coffee Company. All rights reserved."
  disclaimers:
    - { trigger: "rewards_offer", text: "Starbucks Rewards terms apply." }
    - { trigger: "price_shown", text: "Prices and participation may vary." }
  required_hashtags: []                        # campaign-dependent

# --- Language constraints ---
language:
  banned_words: ["cheap", "discount", "deal", "guys"]
  banned_claims: ["healthiest", "best coffee in the world", "#1 coffee"]
  reading_grade_max: 7
  approved_tone_words: ["warm", "genuine", "friendly", "uplifting", "human", "day-making"]

# --- Imagery constraints ---
imagery:
  allowed_subjects: ["coffee & espresso drinks, cups, hands holding cups, cafe interiors, baristas, seasonal moments, food pairings, people connecting"]
  banned_subjects: ["alcohol", "competitor brands/cups", "overtly staged stock clichés", "anything implying health claims"]
  style: "warm natural light, rich greens & creams, shallow depth of field, inviting and human, the cup as hero"
  must_avoid: ["text rendered in image", "logos rendered in image", "extra fingers", "misshapen cups/lids", "fake-looking foam"]
  color_grade: "warm, slightly green-leaning, comfortable contrast"
  aspect_ratios: ["1:1", "4:5", "9:16", "16:9"]

# --- Accessibility ---
accessibility:
  min_contrast_ratio: 4.5
  min_text_size_px: 14
```

---

# PART B — Brand Guidance (soft, for RAG)

## B1. Brand essence
Starbucks is the "third place" between home and work — a warm, human moment built around handcrafted coffee. It sells connection and a small daily lift, not just caffeine. The experience is the product.

## B2. Personality & voice
Informal, genuine, friendly, and human. Starbucks runs a **two-tone voice**:
- **Functional** — clear and helpful; organizes and anticipates needs (ordering, wayfinding, rewards mechanics). Calls attention to the product, not itself. Clear, never sterile.
- **Expressive** — where personality "unfurls with day-making thoughts," used on focal products to present a product truth in a fresh, warm way.

- We sound: warm, genuine, friendly, uplifting, human.
- We never sound: pushy, salesy, discount-driven, corporate, cold.
- Say this: "Your fall, in a cup." · Not that: "50% OFF pumpkin drinks — today only!"

## B3. Audience & their interests
A broad base anchored by daily ritual customers and Rewards members. They value routine, small comforts, seasonal moments, and a sense of belonging. They lean in for: familiar favorites, seasonal newness (PSL season is cultural), personalization of their order, and the feeling of being known by their "third place." They scroll past hard-sell discounting and anything that feels impersonal.

## B4. Mood & visual feeling
Warm morning light, the comfort of a held cup, greens and creams, hands and steam, a quiet uplift. Seasonal shifts in palette and props (autumn warmth, holiday red-and-green within brand, summer brightness) but always returning to the cup as hero and the human moment around it.

## B5. Do's and don'ts (with reasons)
- DO lead with the drink and the moment — because the experience is what's sold, not a price.
- DO use seasonal relevance — because seasonal launches are cultural events customers anticipate.
- DON'T use the word "discount/deal/cheap" — because it cheapens a premium, experience-led brand.
- DON'T render the Siren on busy imagery without a scrim — because logo integrity is non-negotiable.
- DON'T over-personalize literally ("Hi Junho, your usual grande latte") unless data is high-confidence and the channel is appropriate — because it can feel surveillant.

## B6. Exemplar campaigns
- **Seasonal launch (PSL / Red Cups)** — a single hero drink, warm grade, minimal expressive copy. Works because it turns a product into a seasonal ritual.
- **Rewards "free favorite" moments** — functional clarity + warm reward framing. Works because it makes the mechanic feel like a gift, not a promo.

## B7. Anti-examples
- Loud percentage-off banners in non-brand red — off-brand: discounting tone, wrong color.
- Cluttered multi-product grids — off-brand: dilutes the single warm moment.

## B8. Messaging pillars
1. **Ritual & comfort** — the daily lift (proof: routine, familiar favorites).
2. **Seasonal moments** — newness you look forward to (proof: PSL, holiday).
3. **Belonging / third place** — you're known here (proof: Rewards, personalization).
4. **Craft** — handcrafted by a barista (proof: the make, quality of beans).

## B9. Personalization guidance
Fair-game signals: Rewards purchase history, favorite drink/category, store/time patterns, season, location, lifecycle (new/loyal/lapsed). Off-limits: sensitive inferences, anything implying tracking. Default to **inferential** personalization (match mood, product, season) and reserve **literal** references for high-confidence Rewards data in owned channels (app/email). Always have a no-data fallback: brand essence + a seasonal hero drink.

---

# PART C — Personalization Instantiation (per `Personalization-Design-System.md` §8)

**Product categories → playbooks:**
| Starbucks category | Playbook (§5) | Notes |
|---|---|---|
| Seasonal beverages (PSL, holiday) | Consumable + Experiences hybrid | Ritual + anticipation; hero drink, seasonal mood. |
| Core beverages (latte, cold brew) | Consumable / repeat-purchase | Ritual & replenishment; subscription-like via Rewards. |
| Food pairings | Consumable | Secondary; pairs with a drink, never the sole hero. |
| Rewards / app | Services / subscription | Outcome = belonging + free favorites; functional voice leads. |
| Merch (cups, tumblers) | Gifting / occasion | Seasonal gifting; the gesture. |

**Available signals & confidence (test assumption):** Rewards purchase history (high), favorite drink (high, expressed), visit time/frequency (high, behavioral), lifecycle status (high), season/location/weather (high, contextual), inferred preferences (medium). PII used in imagery/copy: **no**.

**Literalness ceiling:** inferential by default; literal allowed only for Rewards members in owned channels (app/email), never in paid social.

**No-data fallback ad:** brand-essence + current seasonal hero drink, warm hero image, Siren, expressive one-liner, no offer.

**Banned signals:** none beyond the §6 sensitive categories.

---

## Sources
- [Starbucks Creative Expression — Color](https://creative.starbucks.com/color/)
- [Starbucks Creative Expression — Typography](https://creative.starbucks.com/typography/)
- [Starbucks Creative Expression — Voice](https://creative.starbucks.com/voice/)
- [Starbucks Colors — Hex/RGB/CMYK/Pantone](https://usbrandcolors.com/starbucks-colors/)
- [Starbucks Brand Colors — #00704A](https://chromacreator.com/brands/starbucks)
