"""
Project AD — Reference-style extraction
=======================================
Condition generation on uploaded REFERENCE ADS so new ads inherit their look.
Extracts a lightweight *style profile* — dominant palette, how busy/minimal the
composition is, and overall tone — from the reference images, then turns it into
a prompt phrase + a palette the renderer uses. Abstract style attributes only
(not the reference content).

No heavy ML deps: PIL + numpy + sklearn KMeans (always run). When a Gemini key is
present, a vision-LLM analyst (`llm_agent.analyze_style_vision`, free text tier)
adds a richer read under `style["vision"]` — it augments, never replaces, the
numeric profile, so the interface (a style dict) is unchanged when it's absent.
"""
import os
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

_LUMA = np.array([0.2126, 0.7152, 0.0722])

# Vision-LLM style profiles are cached per reference set (keyed by sorted paths)
# so we don't re-hit the API on every project-page view / regenerate.
_VISION_CACHE = {}
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif"}


def _mime(path):
    return _MIME.get(os.path.splitext(path)[1].lower(), "image/png")


def _vision_profile(paths):
    """Ask the vision-LLM (free text tier) for a richer style profile, or None.

    Cached per reference set. Returns a dict (style_summary, composition, mood,
    lighting, color_feel, texture, typography, prompt_phrase) or None when there
    is no Gemini key / SDK, or on any error — the numeric profile stands alone.
    """
    key = tuple(sorted(paths))
    if key in _VISION_CACHE:
        return _VISION_CACHE[key]
    try:
        import llm_agent
    except Exception:
        _VISION_CACHE[key] = None
        return None
    imgs = []
    for p in list(key)[:4]:
        try:
            with open(p, "rb") as f:
                imgs.append((f.read(), _mime(p)))
        except Exception:
            pass
    profile = llm_agent.analyze_style_vision(imgs) if imgs else None
    _VISION_CACHE[key] = profile
    return profile


def _small(path, size=200):
    im = Image.open(path).convert("RGB")
    im.thumbnail((size, size))
    return np.asarray(im, dtype=float)


def _hex(c):
    return "#%02X%02X%02X" % (int(c[0]), int(c[1]), int(c[2]))


def _sat(c):
    mx, mn = max(c), min(c)
    return (mx - mn) / (mx + 1e-6)


def analyze_references(paths, k=4, vision=True):
    """Return a style profile dict from reference images, or None if none usable.

    The numeric profile (palette + busy/bright/warm/contrast) always runs. When
    `vision` and a Gemini key are present, a richer vision-LLM read is attached
    under `style["vision"]`; it never replaces the numeric profile, only adds to it.
    """
    arrs = []
    for p in paths:
        try:
            arrs.append(_small(p))
        except Exception:
            pass
    if not arrs:
        return None

    px = np.vstack([a.reshape(-1, 3) for a in arrs])
    if len(px) > 20000:
        px = px[np.random.default_rng(0).choice(len(px), 20000, replace=False)]

    kk = max(2, min(k, len(px)))
    km = KMeans(n_clusters=kk, n_init=4, random_state=0).fit(px)
    order = np.argsort(np.bincount(km.labels_))[::-1]         # most common first
    centers = km.cluster_centers_[order]
    palette = [tuple(int(v) for v in c) for c in centers]

    # busyness: mean gradient magnitude (flat/minimal -> low, textured -> high)
    def busy(a):
        g = a.mean(2)
        return (np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean()) / 2
    busyness = min(float(np.mean([busy(a) for a in arrs])) / 25.0, 1.0)

    lum = px @ _LUMA
    brightness = float(lum.mean()) / 255.0
    warmth = float(px[:, 0].mean() - px[:, 2].mean()) / 255.0   # R - B
    contrast = min(float(lum.std()) / 128.0, 1.0)

    profile = {
        "palette": palette,
        "hex_palette": [_hex(c) for c in palette],
        "busyness": round(busyness, 2), "brightness": round(brightness, 2),
        "warmth": round(warmth, 2), "contrast": round(contrast, 2),
        "busyness_label": ("minimal and flat" if busyness < 0.25 else
                           "moderately detailed" if busyness < 0.5 else "detailed and textured"),
        "brightness_label": ("dark" if brightness < 0.40 else
                             "light and airy" if brightness > 0.65 else "mid-toned"),
        "warmth_label": ("warm" if warmth > 0.05 else "cool" if warmth < -0.05 else "neutral"),
        "contrast_label": ("low-contrast" if contrast < 0.40 else
                           "high-contrast" if contrast > 0.80 else "balanced-contrast"),
    }
    if vision:
        v = _vision_profile(paths)
        if v:
            profile["vision"] = v
    return profile


def render_palette(style):
    """Two tones for the background renderer: (accent = most colorful, deep = a darker shade)."""
    pal = style["palette"]
    accent = max(pal, key=_sat)
    deep = min(pal, key=sum)
    if sum(deep) >= sum(accent):                 # not meaningfully darker -> derive one
        deep = tuple(int(c * 0.4) for c in accent)
    return accent, deep


def style_to_prompt(style):
    """A phrase to fold into the image prompt so the model matches the reference style."""
    if not style:
        return ""
    pal = ", ".join(style["hex_palette"][:3])
    phrase = (f" Match the visual STYLE of the reference ads: a limited palette of {pal}; a "
              f"{style['busyness_label']}, {style['brightness_label']}, {style['warmth_label']}, "
              f"{style['contrast_label']} look.")
    vp = (style.get("vision") or {}).get("prompt_phrase")
    if vp:
        phrase += " " + vp.strip()
    return phrase
