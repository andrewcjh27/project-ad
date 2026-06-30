"""
Project AD — Brand-Fit Score (QC on ANY image)
==============================================
Exposes the brand QC judgment as a standalone, explainable score for an
ARBITRARY image — not only ads this system generated. "How on-brand is this,
and why." Handy as a check on external/candidate creative, and as the seam where
a real vision critic drops in.

WHAT IT MEASURES (the spec-free subset of the pipeline's QC):
  - brand_color_coverage: fraction of the frame near the brand palette.
  - taste: a deterministic STAND-IN proxy (brand-color fit + visual contrast)
    behind a `get_vision()` seam — swap in a hosted vision model for real taste.

LIMITATION (by design): without an ad-spec or a vision model the score is coarse
and color/contrast-driven. The in-pipeline BrandGuardian + Critic remain the
authoritative, spec-aware gates; this is the portable, any-image surface. The
`is_brand_color` primitive is shared with BrandGuardian so "a brand-colored
pixel" is single-sourced.
"""
import sys
import numpy as np
from PIL import Image


def color_distance(rgb, target):
    """Euclidean RGB distance (the primitive BrandGuardian's logo check uses)."""
    return float(np.sqrt(sum((a - b) ** 2 for a, b in zip(rgb[:3], target))))


def is_brand_color(rgb, colors, tol=40.0):
    """True if `rgb` is within `tol` of ANY brand color (single-sourced notion)."""
    return any(color_distance(rgb, c) < tol for c in colors)


def brand_colors(brand_id="starbucks"):
    """Distinctive brand palette (deferred import keeps the modules decoupled)."""
    from generation_pipeline import BRAND   # single source of truth for brand config
    c = BRAND["colors"]
    return [c["primary"], c["secondary"], c["cream"]]


def _arr(img):
    return np.asarray(img.convert("RGB"), dtype=float).reshape(-1, 3)


def color_coverage(img, colors, tol=40.0):
    """Fraction of pixels within `tol` of any brand color (vectorized)."""
    px = _arr(img)
    mind = None
    for c in colors:
        d = np.sqrt(((px - np.array(c, dtype=float)) ** 2).sum(axis=1))
        mind = d if mind is None else np.minimum(mind, d)
    return float((mind < tol).mean())


def void_fraction(img):
    """Fraction of the frame that is transparent or near-black — i.e. NOT composed.

    A finished ad fills its frame; a bare product cutout leaves large empty/
    transparent voids. This separates a designed ad from a raw asset.
    """
    transp = 0.0
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alpha = np.asarray(img.convert("RGBA"))[..., 3].reshape(-1)
        transp = float((alpha < 16).mean())
    px = _arr(img)
    near_black = float((np.sqrt((px ** 2).sum(axis=1)) < 30).mean())
    return max(transp, near_black)


# ── Vision seam (mirrors llm_agent.get_llm): a real taste model drops in here ──
def get_vision():
    """Return a hosted vision critic when wired, else None (-> heuristic stand-in).

    Drop a provider in behind this seam (same shape as llm_agent's providers):
    take an image + brand_id, return a 0..1 taste score. Kept None until a key
    and adapter are added, so scoring stays deterministic and offline by default.
    """
    return None


def _taste_heuristic(img):
    """Deterministic STAND-IN for a vision critic: is this a finished, composed frame?"""
    return round(1.0 - min(void_fraction(img) / 0.10, 1.0), 3)


def score_image(img, brand_id="starbucks"):
    """Return {score, verdict, gates, reasons} for how on-brand `img` looks.

    Blends brand-color presence (is the palette there?) with a taste signal
    (is it a finished, composed frame — or a bare cutout?). The vision seam
    replaces the taste heuristic with a real critic when wired.
    """
    colors = brand_colors(brand_id)
    cov = color_coverage(img, colors)
    fit = min(cov / 0.20, 1.0)
    vision = get_vision()
    if vision:
        taste, taste_src = vision.score(img, brand_id), vision.name
    else:
        taste, taste_src = _taste_heuristic(img), "heuristic(stand-in)"

    gates = {
        "brand_color_coverage": round(cov, 3),
        "brand_color_present": "pass" if cov >= 0.04 else "fail",
        "frame_composed": "pass" if taste >= 0.5 else "fail",
    }
    score = round(min(0.99, 0.5 * fit + 0.5 * taste), 2)
    verdict = "on-brand" if score >= 0.6 else ("borderline" if score >= 0.4 else "off-brand")
    reasons = [
        f"{cov*100:.1f}% of the frame sits in the brand palette",
        f"composed-frame {taste:.2f} via {taste_src}",
    ]
    return {"score": score, "verdict": verdict, "gates": gates,
            "taste": taste, "taste_source": taste_src, "reasons": reasons}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "sbux_psl_ad.png"
    brand = sys.argv[2] if len(sys.argv) > 2 else "starbucks"
    res = score_image(Image.open(path), brand)
    print(f"brand-fit ({brand}): {path}")
    print(f"  score   : {res['score']}  -> {res['verdict']}")
    for k, v in res["gates"].items():
        print(f"  {k:22s}: {v}")
    for r in res["reasons"]:
        print(f"  - {r}")
