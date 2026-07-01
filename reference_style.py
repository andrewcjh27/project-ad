"""
Project AD — Reference-style extraction
=======================================
Condition generation on uploaded REFERENCE ADS so new ads inherit their look.
Extracts a lightweight *style profile* — dominant palette, how busy/minimal the
composition is, and overall tone — from the reference images, then turns it into
a prompt phrase + a palette the renderer uses. Abstract style attributes only
(not the reference content).

No heavy ML deps: PIL + numpy + sklearn KMeans (already required). A vision-LLM
analyst can later drop in behind `analyze_references()` for a richer profile
(the interface — a style dict — stays the same).
"""
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

_LUMA = np.array([0.2126, 0.7152, 0.0722])


def _small(path, size=200):
    im = Image.open(path).convert("RGB")
    im.thumbnail((size, size))
    return np.asarray(im, dtype=float)


def _hex(c):
    return "#%02X%02X%02X" % (int(c[0]), int(c[1]), int(c[2]))


def _sat(c):
    mx, mn = max(c), min(c)
    return (mx - mn) / (mx + 1e-6)


def analyze_references(paths, k=4):
    """Return a style profile dict from reference images, or None if none usable."""
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

    return {
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
    return (f" Match the visual STYLE of the reference ads: a limited palette of {pal}; a "
            f"{style['busyness_label']}, {style['brightness_label']}, {style['warmth_label']}, "
            f"{style['contrast_label']} look.")
