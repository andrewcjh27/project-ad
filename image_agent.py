"""
Project AD — Image Generator Agent (real-model integration)
===========================================================
Swappable provider adapter for the Image Generator role (Agent #5).
The pipeline calls `get_image_provider().generate(...)`; the concrete provider
is chosen from whichever API key is present in the environment. If none is set,
it falls back to the offline procedural hero so the demo always runs.

Wire it up by exporting ONE of:
    export GEMINI_API_KEY=...             # uses Gemini 2.5 Flash Image ("nano banana")
    export OPENAI_API_KEY=sk-...          # uses OpenAI gpt-image-1
    export REPLICATE_API_TOKEN=r8_...     # uses Flux 1.1 Pro on Replicate

Install whichever you use:
    pip install google-genai  # for Gemini / nano banana
    pip install openai        # for OpenAI
    pip install replicate     # for Replicate/Flux
    pip install pillow requests

The brand imagery rules + negative prompt come from the ad-spec, so output stays
on-brand regardless of provider (see Starbucks-Brand-Package.md imagery block).
"""

import os, io, math
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    raise SystemExit("pip install pillow")


# ---- size mapping: ad aspect ratio -> nearest provider-supported size --------
def _portrait_size(w, h):
    """Most providers want specific buckets; pick nearest for a 4:5/9:16 ad."""
    ar = w / h
    if ar < 0.65:   return (1024, 1792)   # tall (9:16-ish)
    if ar < 0.95:   return (1024, 1280)   # portrait (4:5-ish)
    if ar > 1.5:    return (1792, 1024)   # wide
    return (1024, 1024)                    # square


def _aspect_ratio(w, h):
    """Map a target size to the nearest aspect ratio string (Gemini image_config)."""
    ar = w / h
    if ar < 0.65:   return "9:16"
    if ar < 0.95:   return "4:5"
    if ar > 1.5:    return "16:9"
    if ar > 1.05:   return "4:3"
    return "1:1"


def _compose_prompt(prompt, negative):
    """Fold a negative prompt into the text for models that lack a negative field."""
    try:
        from ad_brief import PHOTO_TAG          # single source for the style tag
        tag = PHOTO_TAG
    except Exception:
        tag = "minimal abstract graphic design, clean and uncluttered, no text, no logos"
    neg = f" Avoid: {negative}." if negative else ""
    return f"{prompt}.{neg} {tag}."


# ============================================================================
# Providers
# ============================================================================
class ImageProvider:
    name = "base"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        raise NotImplementedError


class GeminiImageProvider(ImageProvider):
    """Gemini 2.5 Flash Image — aka "nano banana" (Google google-genai SDK)."""
    name = "gemini:gemini-2.5-flash-image"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        from google import genai
        from google.genai import types
        client = genai.Client()                        # reads GEMINI_API_KEY / GOOGLE_API_KEY
        resp = client.models.generate_content(
            model="gemini-2.5-flash-image",            # "nano banana"
            contents=_compose_prompt(prompt, negative),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=_aspect_ratio(width, height)),
            ),
        )
        data = next((p.inline_data.data for p in resp.candidates[0].content.parts
                     if getattr(p, "inline_data", None) and p.inline_data.data), None)
        if data is None:
            raise RuntimeError("Gemini returned no image data")
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img.resize((width, height))


class OpenAIImageProvider(ImageProvider):
    name = "openai:gpt-image-1"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        from openai import OpenAI
        import base64
        client = OpenAI()                              # reads OPENAI_API_KEY
        w, h = _portrait_size(width, height)
        # gpt-image-1 supports 1024x1024, 1024x1536, 1536x1024 — map to nearest
        size = "1024x1536" if h > w else ("1536x1024" if w > h else "1024x1024")
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=_compose_prompt(prompt, negative),
            size=size, n=1,
        )
        data = base64.b64decode(resp.data[0].b64_json)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img.resize((width, height))


class ReplicateFluxProvider(ImageProvider):
    name = "replicate:flux-1.1-pro"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        import replicate, requests
        ar = "9:16" if (width / height) < 0.65 else ("4:5" if width < height else
             ("16:9" if width > height else "1:1"))
        out = replicate.run(
            "black-forest-labs/flux-1.1-pro",
            input={
                "prompt": _compose_prompt(prompt, negative),
                "aspect_ratio": ar,
                "output_format": "png",
                "safety_tolerance": 2,
                **({"seed": int(seed)} if seed is not None else {}),
            },
        )
        url = out[0] if isinstance(out, list) else out
        img = Image.open(io.BytesIO(requests.get(url, timeout=60).content)).convert("RGB")
        return img.resize((width, height))


# Offline background styles (no API). Change the default here or set AD_BG_STYLE.
#   diverse  pick a different minimal form + parameters from the seed (varies each run)
#   gradient | flat | circle | vignette | block  pin one specific style
PROCEDURAL_STYLE = "diverse"

class ProceduralProvider(ImageProvider):
    """Offline fallback — minimal procedural backgrounds in the brand color (no API).

    Style from AD_BG_STYLE env, else PROCEDURAL_STYLE. In "diverse" mode the seed
    chooses one minimal form (gradient / flat / vignette / circle) AND varies its
    parameters (direction, glow position, circle placement, tone), so successive
    runs produce genuinely different — but still minimal and on-palette — designs.
    The seed is recorded in the spec, so any specific ad stays reproducible.
    """
    name = "procedural(fallback)"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        style = os.getenv("AD_BG_STYLE", PROCEDURAL_STYLE)
        rng = np.random.default_rng(seed if seed is not None else 0)
        pal = palette or ((0xC9, 0x8A, 0x5E), (0x3A, 0x24, 0x18))
        accent, deep = np.array(pal[0], float), np.array(pal[1], float)
        white = np.array((250, 250, 248), float)
        H, W = height, width
        yy = np.linspace(0, 1, H)[:, None, None]
        xx = np.linspace(0, 1, W)[None, :, None]
        if style == "diverse":
            style = str(rng.choice(["gradient", "flat", "vignette", "circle"]))
        tone = accent if rng.random() < 0.7 else (0.6 * accent + 0.4 * deep)   # vary the brand tone
        if style == "flat":
            base = (rng.uniform(0.35, 0.55) * tone + rng.uniform(0.45, 0.65) * white).reshape(1, 1, 3)
        elif style == "block":
            base = np.where(yy < rng.uniform(0.55, 0.70), white, tone)          # split varies
        elif style == "circle":
            cy, cx, r = rng.uniform(0.26, 0.40), rng.uniform(0.42, 0.58), rng.uniform(0.22, 0.30)
            ar = W / H
            base = np.where(((yy - cy) ** 2 + ((xx - cx) * ar) ** 2) < r ** 2, tone, white)
        elif style == "vignette":
            oy, ox, rad = rng.uniform(0.85, 1.05), rng.uniform(0.35, 0.65), rng.uniform(0.70, 0.95)
            g = np.clip(1 - np.sqrt((yy - oy) ** 2 + (xx - ox) ** 2) / rad, 0, 1)
            base = white * (1 - g) + tone * g                                   # glow position varies
        else:                                                                   # gradient, direction varies
            d = rng.uniform(0.0, 0.4)
            t = (1 - d) * yy + d * xx
            base = white * (1 - t) + tone * t
        grain = rng.normal(0, 3, (H, W, 1))
        return Image.fromarray(np.clip(base + grain, 0, 255).astype("uint8"), "RGB")


# ============================================================================
# Factory
# ============================================================================
def get_image_provider(prefer=None):
    """Pick a provider by env keys (or `prefer` name). Always returns something.

    AD_IMAGE_PROVIDER overrides auto-detection: set it to "procedural" to keep
    images free (e.g. use a Gemini key for LLM copy but not paid image gen), or
    to "gemini" / "openai" / "replicate" to force one.
    """
    prefer = prefer or os.getenv("AD_IMAGE_PROVIDER")
    if prefer == "procedural":
        return ProceduralProvider()
    if prefer == "gemini" or (prefer is None and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))):
        try:
            from google import genai  # noqa
            return GeminiImageProvider()
        except ImportError:
            pass
    if prefer == "openai" or (prefer is None and os.getenv("OPENAI_API_KEY")):
        try:
            import openai  # noqa
            return OpenAIImageProvider()
        except ImportError:
            pass
    if prefer == "replicate" or (prefer is None and os.getenv("REPLICATE_API_TOKEN")):
        try:
            import replicate  # noqa
            return ReplicateFluxProvider()
        except ImportError:
            pass
    return ProceduralProvider()


if __name__ == "__main__":
    p = get_image_provider()
    print("Active image provider:", p.name)
    img = p.generate(
        "overhead pumpkin spice latte on a worn oak cafe table, autumn morning light",
        "text, logos, watermark, extra fingers", 1080, 1350, seed=771204,
        palette=((0xC9, 0x8A, 0x5E), (0x3A, 0x24, 0x18)),
    )
    img.save("hero_test.png")
    print("Saved hero_test.png via", p.name)
