"""
Project AD — LLM Agent adapter (Art Director / Copywriter brains)
=================================================================
The Art Director and Copywriter GENERATE the image prompt and copy from data.
This adapter gives them an LLM when a key is present, and a deterministic,
STILL-DATA-DRIVEN fallback when offline (composes from the structured inputs
rather than returning a frozen string).

Wire a real model by exporting ONE of:
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

def get_llm():
    if os.getenv("OPENAI_API_KEY"):
        try: import openai; return _OpenAI()      # noqa
        except ImportError: pass
    if os.getenv("ANTHROPIC_API_KEY"):
        try: import anthropic; return _Anthropic() # noqa
        except ImportError: pass
    return None                                    # -> caller uses data-driven fallback


# ── Art Director: generate the IMAGE PROMPT from data ───────────────────────
def generate_image_prompt(product, segment, brand_style, negative, photo_tag):
    """LLM-write the hero image prompt from product + segment + brand style."""
    llm = get_llm()
    if llm:
        system = ("You are an advertising Art Director. Write ONE vivid image-generation "
                  "prompt for the hero photo of an ad. Describe only the scene/subject — "
                  "never include text or logos in the image. 1-2 sentences.")
        user = json.dumps({"product": product, "audience_segment": segment,
                           "brand_style": brand_style})
        subject = llm.complete(system, user)
        return f"{subject} {photo_tag}.", f"generated:{llm.name}"
    # ---- data-driven deterministic fallback (composed from the inputs) ------
    setting = _setting_from_segment(segment)
    subject = f"{product['name']} — {product['descriptors']} — in {setting}"
    return f"{subject}, {brand_style}. {photo_tag}.", "generated:rule-based(from data)"


# ── Copywriter: generate HEADLINE + SUBHEAD from data ───────────────────────
def generate_copy(product, segment, angle):
    llm = get_llm()
    if llm:
        system = ("You are a brand Copywriter. Write a short ad HEADLINE (<=6 words) and a "
                  "one-line SUBHEAD in a warm, premium voice. Return JSON {\"headline\":..,\"subhead\":..}.")
        user = json.dumps({"product": product, "audience_segment": segment, "angle": angle})
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
