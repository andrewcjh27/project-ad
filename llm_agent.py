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
def generate_image_prompt(product, segment, brand_style, negative, photo_tag, exemplars=None):
    """LLM-write the hero image prompt from product + segment + brand style.

    `exemplars` (optional) are retrieved past on-brand ads used as few-shot
    guidance for the LLM path; the offline fallback ignores them.
    """
    llm = get_llm()
    if llm:
        system = ("You are an award-winning luxury advertising art director designing a premium campaign hero "
                "background image. Write ONE image-generation prompt (2-3 sentences) for a minimalist, "
                "high-end advertising scene designed specifically as a backdrop for product placement. "
                "Create a visually striking composition with one dominant atmospheric environment and a "
                "deliberately reserved clean area where the product will be placed later. Treat the empty "
                "space as an intentional design element: elegant, balanced, and naturally integrated into "
                "the composition rather than blank. "
                "Use sophisticated lighting, premium materials, subtle depth, and a restrained color palette "
                "aesthetic inspired by luxury fashion, beauty, and technology campaigns. Keep the scene "
                "simple, modern, and timeless with strong visual hierarchy. "
                "Describe only the photograph; never include the product itself, text, words, logos, labels, "
                "UI, or graphic elements.")
        payload = {"product": product, "audience_segment": segment, "brand_style": brand_style}
        if exemplars:
            system += _EXEMPLAR_GUIDANCE
            payload["past_on_brand_examples"] = _exemplars_for_prompt(exemplars)
        subject = llm.complete(system, json.dumps(payload))
        return f"{subject} {photo_tag}.", f"generated:{llm.name}"
    # ---- data-driven deterministic fallback (composed from the inputs) ------
    setting = _setting_from_segment(segment)
    subject = f"{product['name']} — {product['descriptors']} — in {setting}"
    return f"{subject}, {brand_style}. {photo_tag}.", "generated:rule-based(from data)"


# ── Copywriter: generate HEADLINE + SUBHEAD from data ───────────────────────
def generate_copy(product, segment, angle, exemplars=None):
    llm = get_llm()
    if llm:
        system = ("You are a brand Copywriter. Write a short ad HEADLINE (<=6 words) and a "
                  "one-line SUBHEAD in a warm, premium voice. Return JSON {\"headline\":..,\"subhead\":..}.")
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
    daypart = segment.get("daypart", "day")
    pillar = segment.get("pillar", "ritual")
    head = {
        "seasonal": f"Your {daypart}, now in {product['flavor']}.",
        "belonging": f"Your {name} is waiting.",
        "ritual": f"{name}. Made for your {daypart}.",
    }.get(pillar, f"{name}, made for you.")
    sub = {
        "loyal":  "Order ahead and skip the wait.",
        "lapsed": "Here's your favorite, on us.",
        "new":    "Handcrafted, every single cup.",
        "vip":    "A little something, just for you.",
    }.get(segment.get("lifecycle", "loyal"), "Made for your moment.")
    return head, sub, "generated:rule-based(from data)"


def _setting_from_segment(segment):
    season = segment.get("season", "")
    daypart = segment.get("daypart", "")
    bits = [b for b in [f"{season} {daypart}".strip(), "a cozy cafe table"] if b]
    return ", ".join(bits) if bits else "a warm cafe setting"
