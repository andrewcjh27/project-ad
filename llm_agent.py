"""
Project AD — LLM Agent adapter (Art Director / Copywriter brains)
=================================================================
The Art Director and Copywriter GENERATE the image prompt and copy from data.
This adapter gives them an LLM when a key is present, and a deterministic,
STILL-DATA-DRIVEN fallback when offline (composes from the structured inputs
rather than returning a frozen string).

Wire a real model by exporting ONE of:
    export GEMINI_API_KEY=...         (pip install google-genai)   # same key as nano banana
    export OPENAI_API_KEY=sk-...      (pip install openai)
    export ANTHROPIC_API_KEY=...      (pip install anthropic)
"""

import os, json


# ── Providers ───────────────────────────────────────────────────────────────
class _OpenAI:
    name = "openai:gpt-4o-mini"
    def complete(self, system, user):
        from openai import OpenAI
        r = OpenAI().chat.completions.create(
            model="gpt-4o-mini", temperature=0.8,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        return r.choices[0].message.content.strip()

class _Anthropic:
    name = "anthropic:claude"
    def complete(self, system, user):
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model="claude-3-5-sonnet-latest", max_tokens=300, system=system,
            messages=[{"role": "user", "content": user}])
        return r.content[0].text.strip()

class _Gemini:
    name = "gemini:gemini-2.5-flash"
    def complete(self, system, user):
        from google import genai
        from google.genai import types
        r = genai.Client().models.generate_content(    # reads GEMINI_API_KEY / GOOGLE_API_KEY
            model="gemini-2.5-flash", contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.8))
        return r.text.strip()

def get_llm():
    # Prefer Gemini so one GEMINI_API_KEY powers both the art-director text and nano-banana images.
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        try: from google import genai; return _Gemini()  # noqa
        except ImportError: pass
    if os.getenv("OPENAI_API_KEY"):
        try: import openai; return _OpenAI()      # noqa
        except ImportError: pass
    if os.getenv("ANTHROPIC_API_KEY"):
        try: import anthropic; return _Anthropic() # noqa
        except ImportError: pass
    return None                                    # -> caller uses data-driven fallback


# ── Brand-memory exemplars (soft guidance only) ─────────────────────────────
_EXEMPLAR_GUIDANCE = (
    " You are also shown PAST ON-BRAND ADS as `past_on_brand_examples`. Match their "
    "voice, concept logic, and tone — but do NOT copy them verbatim, and NEVER invent "
    "colors, fonts, or logos (those are enforced separately).")

def _exemplars_for_prompt(exemplars):
    """Concept/copy fields only — never brand hard-rules."""
    return [{"headline": e.get("headline", ""), "subhead": e.get("subhead", ""),
             "image_prompt": e.get("image_prompt", "")} for e in (exemplars or [])]


# ── Art Director: generate the IMAGE PROMPT from data ───────────────────────
def generate_image_prompt(product, segment, brand_style, negative, photo_tag,
                          exemplars=None, brand_colors=None, goal=None):
    """LLM-write a DETAILED background-plate prompt from the brief.

    Engineers a rich prompt that names the exact brand colors, states the ad's
    goal/purpose, and specifies composition + craft. `brand_colors` is a dict of
    named hex values; `goal` is the per-group purpose. Falls back to a detailed
    data-driven prompt offline.
    """
    llm = get_llm()
    if llm:
        system = (
            "You are an expert advertising Art Director and image prompt engineer. Using the JSON "
            "brief, write ONE highly detailed, fully-specified image-generation prompt (4-6 sentences) "
            "for the BACKGROUND PLATE of a premium vertical 4:5 poster — a FLAT 2D ABSTRACT GRAPHIC "
            "background (a clean color study, NOT a photograph of any object or place) that sits behind "
            "a product cutout and a short headline. Be precise and descriptive so the model has little "
            "room to drift — state exactly what the surface looks like, its tones, its finish, its "
            "texture, and what occupies each region. Cover, as flowing prose: "
            "(1) PURPOSE — let the brief's `goal` and audience persona set the mood and intent; "
            "(2) PALETTE — choose just TWO or THREE colors from the provided `brand_colors` that fit "
            "the mood (you need not use all); name the exact hex values and use no colors outside that "
            "chosen set; describe precisely how they meet (soft gradient direction, or a flat field); "
            "(3) COMPOSITION & PLACEMENT — minimal and abstract; reserve clean space for the layout: "
            "TOP-LEFT clear for a small logo, UPPER-CENTER calm and empty for the product cutout, and "
            "the LOWER THIRD (especially lower-left) LIGHT and low-contrast so DARK headline and "
            "subhead text stays legible on top; "
            "(4) CRAFT — specify even, soft, diffuse lighting, a fine matte grain or subtle paper "
            "texture, smooth seamless tonal transitions with NO banding, and state it is a flat "
            "vertical 4:5 composition; "
            "(5) CREATIVITY — be genuinely creative and VARY THE APPROACH from one ad to the next "
            "(sometimes a soft gradient, sometimes a flat field, sometimes an off-center glow, "
            "sometimes a single simple geometric form) so successive posters look genuinely "
            "different, while staying strictly minimal. "
            "OVERRIDING PRINCIPLE: EXTREMELY minimal and clean — mostly empty negative space, very few "
            "tonal elements, flat, calm and uncluttered; the detail must add precision, never visual "
            "busyness. HARD RULE: describe ONLY the abstract 2D graphic; never include any text, words, "
            "letters, numbers, logos, UI, people, faces, hands, products, recognizable objects, or any "
            "photographic scene.")
        payload = {"goal": goal, "audience_segment": segment, "product": product,
                   "brand_colors": brand_colors, "brand_style": brand_style}
        if exemplars:
            system += _EXEMPLAR_GUIDANCE
            payload["past_on_brand_examples"] = _exemplars_for_prompt(exemplars)
        subject = llm.complete(system, json.dumps(payload))
        return f"{subject} {photo_tag}.", f"generated:{llm.name}"
    # ---- data-driven deterministic fallback (a detailed minimal abstract plate) ----
    colors = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in (brand_colors or {}).items()) or "the brand palette"
    goal_txt = f" Purpose: {goal}" if goal else ""
    subject = (f"an extremely minimal, clean, flat 2D abstract graphic background for a vertical 4:5 "
               f"poster (a color study, not a photo of any object), built from a limited palette of "
               f"two or three colors chosen from the brand colors ({colors}); a soft {product['flavor']} "
               f"color field with a gentle, smooth gradient and fine matte grain, even diffuse lighting "
               f"and no banding; mostly empty — keep the top-left clear for a logo, the upper-center "
               f"clean for a product cutout, and the lower third light and low-contrast so dark "
               f"headline text stays legible; calm, understated, premium; no recognizable scene, no "
               f"objects, no product, no people, no faces, no hands, no text, no logos.{goal_txt}")
    return f"{subject}, {brand_style}. {photo_tag}.", "generated:rule-based(from data)"


# ── Copywriter: generate HEADLINE + SUBHEAD from data ───────────────────────
def generate_copy(product, segment, angle, exemplars=None):
    llm = get_llm()
    if llm:
        system = ("You are a brand Copywriter. Write a short ad HEADLINE (<=5 words) and a brief "
                  "one-line SUBHEAD in a minimal, understated voice — restrained and confident, "
                  "never hype or hard-sell. Adapt the tone to the brand and audience. Favor clarity "
                  "and white space over cleverness. Return JSON {\"headline\":..,\"subhead\":..}.")
        payload = {"product": product, "audience_segment": segment, "angle": angle}
        if exemplars:
            system += _EXEMPLAR_GUIDANCE
            payload["past_on_brand_examples"] = _exemplars_for_prompt(exemplars)
        user = json.dumps(payload)
        try:
            j = json.loads(llm.complete(system, user))
            return j["headline"], j["subhead"], f"generated:{llm.name}"
        except Exception:
            pass
    # ---- data-driven fallback: pick a frame by the segment's pillar/lifecycle
    name = product["name"]
    pillar = segment.get("pillar", "ritual")
    head = {
        "seasonal":  f"{product['flavor'].title()}, in season.",
        "belonging": f"{name}, yours.",
        "ritual":    f"{name}, daily.",
    }.get(pillar, f"{name}.")
    sub = {
        "loyal":  "Ready when you are.",
        "lapsed": "Good to have you back.",
        "new":    "Made fresh, every cup.",
        "vip":    "Quietly, just for you.",
    }.get(segment.get("lifecycle", "loyal"), "Made for the moment.")
    return head, sub, "generated:rule-based(from data)"


# ── Audience Strategist: fuse a trait-mixture into ONE persona ───────────────
def generate_persona(persona_struct):
    """LLM-write a named persona + narrative + creative angle from a trait mixture.

    Returns (name, summary, creative_angle, source) when an LLM is available,
    else None so the caller falls back to its deterministic blend.
    """
    llm = get_llm()
    if not llm:
        return None
    system = ("You are an audience strategist. You are given a STRUCTURED TRAIT MIXTURE for a "
              "customer cohort — proportions across interest, lifecycle, value, behavior, and "
              "demographics. Fuse the WHOLE mixture into ONE believable, named persona; do not "
              "just restate the largest trait. Return JSON with: name (2-4 words, e.g. 'The "
              "Morning Ritualist'), summary (2-3 sentences describing this blended individual and "
              "what they want), creative_angle (one line for how ads should speak to them — "
              "minimal and understated).")
    try:
        j = json.loads(llm.complete(system, json.dumps(persona_struct)))
        return j["name"], j["summary"], j["creative_angle"], f"generated:{llm.name}"
    except Exception:
        return None
