"""
Project AD — Image Generator Agent (real-model integration)
===========================================================
Swappable provider adapter for the Image Generator role (Agent #5).
The pipeline calls `get_image_provider().generate(...)`; the concrete provider
is chosen from whichever API key is present in the environment. If none is set,
it falls back to the offline procedural hero so the demo always runs.

Wire it up by exporting ONE of:
    export OPENAI_API_KEY=sk-...          # uses OpenAI gpt-image-1
    export REPLICATE_API_TOKEN=r8_...     # uses Flux 1.1 Pro on Replicate

Install whichever you use:
    pip install openai        # for OpenAI
    pip install replicate     # for Replicate/Flux
    pip install pillow requests

The brand imagery rules + negative prompt come from the ad-spec, so output stays
on-brand regardless of provider (see Starbucks-Brand-Package.md imagery block).
"""

import os, io, math

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


def _compose_prompt(prompt, negative):
    """Fold a negative prompt into the text for models that lack a negative field."""
    try:
        from ad_brief import PHOTO_TAG          # single source for the style tag
        tag = PHOTO_TAG
    except Exception:
        tag = "High-end advertising photography, no text, no logos"
    neg = f" Avoid: {negative}." if negative else ""
    return f"{prompt}.{neg} {tag}."


# ============================================================================
# Providers
# ============================================================================
class ImageProvider:
    name = "base"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        raise NotImplementedError


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


class ProceduralProvider(ImageProvider):
    """Offline fallback — warm gradient hero in the product palette (no API)."""
    name = "procedural(fallback)"
    def generate(self, prompt, negative, width, height, seed=None, palette=None):
        top, bot = palette or ((0xC9, 0x8A, 0x5E), (0x3A, 0x24, 0x18))
        img = Image.new("RGB", (width, height), top)
        px = img.load()
        for y in range(height):
            t = y / height
            row = (int(top[0]*(1-t)+bot[0]*t), int(top[1]*(1-t)+bot[1]*t), int(top[2]*(1-t)+bot[2]*t))
            for x in range(width):
                px[x, y] = row
        hi = Image.new("L", (width, height), 0)
        ImageDraw.Draw(hi).ellipse([width*0.18, height*0.10, width*0.82, height*0.55], fill=120)
        hi = hi.filter(ImageFilter.GaussianBlur(160))
        return Image.composite(Image.new("RGB", (width, height), (255, 240, 210)), img, hi)


# ============================================================================
# Factory
# ============================================================================
def get_image_provider(prefer=None):
    """Pick a provider by env keys (or `prefer` name). Always returns something."""
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
