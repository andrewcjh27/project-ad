# Personalization & Creative-Strategy Rulebook

*How audience data and product type drive ad design. This is the system that turns "a brand" + "a person" + "a product" into specific creative decisions the art-director LLM encodes in an ad spec. The brand-identity package says **how the brand may look**; this rulebook says **which of those choices to make for this person and this product**.*

Status: Draft · Pairs with `Brand-Identity-Template.md` and `Ad-Spec-Schema.md`

---

## 1. Mental model

Three inputs collide to produce one ad:

```
   BRAND IDENTITY            AUDIENCE DATA              PRODUCT
 (what's allowed)      (who we're talking to)     (what we're selling)
        │                       │                        │
        └───────────────┬───────┴────────────┬───────────┘
                        ▼                     ▼
                 CREATIVE LEVERS  ──▶  AD SPEC (one ad)
        (concept, imagery, copy, layout, format, tone, offer)
```

- **Brand identity** sets the *boundaries* (colors, fonts, voice, do's/don'ts).
- **Audience data** sets the *angle* (what will make *this* person lean in).
- **Product** sets the *playbook* (how this category of thing is best sold).

The art-director LLM reads all three and picks levers. This document defines the **levers** and the **rules** that map data → levers.

---

## 2. The creative levers (what an ad can vary)

Every personalization decision changes one or more of these. They map 1:1 onto ad-spec fields.

| Lever | What changes | Ad-spec field |
|---|---|---|
| **Concept / angle** | The big idea & emotional hook | `concept` |
| **Imagery** | Subject, scene, mood, who's depicted | `canvas.imagery[].prompt` |
| **Copy angle** | Headline framing, tone, length | `elements[type:text].content` |
| **Layout density** | Minimal vs. information-rich | `elements[]` count & `box`es |
| **Output format** | Image / poster / video; aspect ratio | `output` |
| **Offer / CTA** | What we ask for, how hard the push | `elements[role:cta]` |
| **Color emphasis** | Which approved palette members lead | `elements[].color` refs |
| **Personalization depth** | Literal vs. inferential reference to the person | `personalization.literalness` |

> Note: levers move **within** brand constraints. Data never overrides a hard rule — it chooses among allowed options.

---

## 3. Audience signal taxonomy

The data we may have about a person, grouped by type. For each, mark availability per integration and whether it's permitted (see §6).

| Category | Example signals | Primarily drives |
|---|---|---|
| **Behavioral** | Past purchases, browse/category affinity, cart, time-of-day, frequency, recency | Concept, product choice, offer |
| **Demographic** | Age band, location/region, language | Imagery casting, language, seasonal context |
| **Contextual** | Season, weather, local events, device, placement (feed vs. story) | Format, mood, timeliness |
| **Lifecycle** | New vs. returning, churning, VIP, subscription status | Offer aggressiveness, tone |
| **Expressed** | Wishlist, saved items, stated preferences, survey answers | Concept, copy angle (highest-confidence) |
| **Inferred** | "Values craft over convenience," "price-sensitive," "gift-buyer" | Copy angle, concept framing |

**Confidence matters.** Expressed > behavioral > inferred. Higher-confidence signals license more *literal* personalization; low-confidence signals should stay *inferential* (mood/angle, not "Hi Junho, buy the beans you viewed").

---

## 4. Signal → lever mapping (the rulebook)

These are starter rules. Each brand can override. Format: **when [signal], then [lever decision], because [reason].**

### Behavioral
- When **high category affinity** (repeat buyer of a category) → lead imagery & concept with that category; product = their category's hero SKU. *Show them more of what they already love.*
- When **browsed but didn't buy** → concept = gentle reminder + reassurance (reviews, quality cue); offer = low-friction. *Reduce the hesitation, don't re-sell the want.*
- When **morning/evening browse pattern** → mood & imagery time-of-day match their pattern; format = story/vertical if mobile-evening. *Meet them in their moment.*
- When **lapsed / high recency gap** → concept = "what's new / we missed you"; offer = stronger. *Re-activation needs a reason to return.*

### Lifecycle
- When **new visitor** → concept = brand essence + flagship product; soft offer; format = high-polish hero. *First impression sells the brand, not a discount.*
- When **VIP / loyal** → concept = exclusivity/early-access; minimal offer; premium layout. *Status, not savings.*
- When **churning** → concept = win-back; strongest permitted offer; direct copy. *Highest-intent moment for a push.*

### Contextual
- When **cold-weather region/season** → imagery & product shift to seasonal fit; copy references the season. *Relevance lifts response.*
- When **story/vertical placement** → `output` = 9:16 video or motion poster; copy shortened; single focal element. *Format follows surface.*
- When **local event/holiday** → concept ties to the occasion within brand voice. *Timeliness.*

### Expressed
- When **wishlist/saved item** → product = that exact item; concept = "it's still here / now's the time"; personalization = literal-ok (high confidence). *Their own stated intent.*

### Inferred (use cautiously, keep inferential)
- When **inferred price-sensitive** → copy angle = value/longevity framing (never "cheap"); offer surfaced. *Frame value without cheapening the brand.*
- When **inferred gift-buyer** → concept = giving/occasion; product = giftable SKU/bundle; imagery = two-person or wrapped. *Sell the gesture.*
- When **inferred values-craft** → concept = process/origin story; minimal offer; editorial layout. *Sell the how, not the price.*

> **Conflict resolution:** when signals disagree, the **highest-confidence** signal wins the *concept*; lower-confidence signals may still tune *mood/format*. Record which signals were used and the `literalness` in `personalization`.

---

## 5. Product-type playbooks

Different product categories are sold differently regardless of audience. Each brand instantiates these for its actual catalog. Format per playbook: **default concept · imagery approach · copy emphasis · format · offer posture · layout.**

### Consumable / repeat-purchase (coffee, cosmetics, food)
- Concept: ritual, sensory pleasure, replenishment. Imagery: product in-use, close, warm. Copy: sensory + benefit. Format: 1:1 / 4:5 image or short video. Offer: subscription nudge for repeat buyers. Layout: clean, single hero.

### Considered / high-ticket (electronics, furniture, appliances)
- Concept: confidence, craftsmanship, proof. Imagery: detail + in-context lifestyle. Copy: spec-backed benefit, reassurance. Format: poster/carousel, layout-heavy. Offer: financing/trial, not discount. Layout: information-rich, clear hierarchy.

### Fashion / apparel
- Concept: identity, aspiration, fit-to-self. Imagery: on-body, casting matched to audience demo. Copy: short, evocative. Format: vertical video/story shines. Offer: new-arrival/seasonal. Layout: image-dominant, minimal text.

### Services / subscriptions (SaaS, memberships, finance)
- Concept: outcome & ease; the better life after. Imagery: abstract/illustrative or human-using. Copy: outcome + proof point; clear CTA. Format: poster/layout-heavy (value props need room). Offer: free trial / first-month. Layout: structured, benefit-led.

### Experiences / events / travel
- Concept: anticipation, escape, the feeling of being there. Imagery: immersive, wide, aspirational scene. Copy: invitational, evocative. Format: video / wide hero. Offer: book-now urgency, scarcity if real. Layout: immersive, minimal overlay.

### Gifting / occasion
- Concept: the gesture & the recipient's reaction. Imagery: giving moment, wrapped, two-person. Copy: warm, occasion-anchored. Format: image or short video. Offer: bundle / deadline (shipping cutoff). Layout: warm, single focal.

---

## 6. Personalization guardrails (brand-overridable)

- **Confidence gates literalness.** Only expressed or strong behavioral signals license literal personalization ("the jacket you saved"). Inferred signals stay at mood/angle level.
- **No creepiness.** Never surface sensitive inferences (health, finances, protected attributes) or imply surveillance. If a signal would feel invasive said out loud, don't reference it literally.
- **PII never rendered** into ad imagery or copy unless the brand explicitly allows and the channel is appropriate.
- **Fallback path required.** Every rule must degrade gracefully when data is missing → fall back to brand-flagship + brand-essence concept. A no-data ad must still be excellent.
- **Brand voice always wins.** A personalization angle that violates the brand's banned words/claims is discarded, not bent.
- Record on every ad: `signals_used`, `inference`, `literalness`, `pii_used`, `off_limits_respected` (see ad-spec `personalization`).

---

## 7. How the art-director LLM uses this

At generation time, the art-director receives: the brand package (config + RAG), the audience signal payload, and the target product. Its procedure:

1. **Select product playbook** (§5) from the product's category → baseline creative posture.
2. **Read audience signals**, rank by confidence (§3).
3. **Apply signal→lever rules** (§4) to adjust concept, imagery, copy angle, format, offer.
4. **Resolve conflicts** by confidence; set `personalization.literalness` accordingly.
5. **Check guardrails** (§6); drop any angle that breaks brand rules or guardrails.
6. **Emit the ad spec** with `concept`, `canvas`, `elements`, `personalization` filled — every choice traceable to a rule.

This makes every ad's personalization **explainable** (which rule fired, which signal drove it) — essential for the human reviewer and the feedback loop that tunes these rules over time.

---

## 8. Per-brand instantiation checklist
- [ ] List the brand's actual product categories and bind each to a §5 playbook (customize defaults).
- [ ] Map available audience signals per integration; mark confidence and permission.
- [ ] Override/extend §4 rules where the brand differs.
- [ ] Define the brand's literalness ceiling and any banned signals (§6).
- [ ] Define the no-data fallback ad for this brand.
- [ ] Review with the embedded designer + legal before first live use.
```
