"""
Project AD — Web generator
==========================
Renders ONE minimal, on-brand poster from a project's data: the brand color
drives a diverse minimal background (reusing image_agent.ProceduralProvider),
and the project's interest/headline + logo + optional product cutout are
composited on top. Aligned to the brand + interest; diverse per seed.
"""
import os
import sys
import random

# Make the repo-root modules (image_agent) importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont       # noqa: E402
from image_agent import ProceduralProvider        # noqa: E402

W, H = 1080, 1350
INK = (20, 17, 15)
MARGIN = 80


def _hex_to_rgb(h):
    h = (h or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (136, 136, 136)


def _darken(rgb, f=0.35):
    return tuple(int(c * f) for c in rgb)


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Georgia.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _paste_contained(canvas, path, box):
    """Paste a transparent image scaled to fit `box` (x,y,w,h), centered."""
    img = Image.open(path).convert("RGBA")
    x, y, bw, bh = box
    scale = min(bw / img.width, bh / img.height)
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    img = img.resize((nw, nh))
    canvas.paste(img, (x + (bw - nw) // 2, y + (bh - nh) // 2), img)


def generate_poster(project, out_path, seed=None):
    """Render the project's poster. Returns (out_path, seed_used)."""
    accent = _hex_to_rgb(project.get("brand_primary"))
    deep = (_hex_to_rgb(project["brand_secondary"])
            if project.get("brand_secondary") else _darken(accent))
    seed = seed if seed is not None else random.randint(1, 2**31 - 1)

    # Diverse minimal background in the brand color (same engine as the pipeline).
    canvas = ProceduralProvider().generate("", "", W, H, seed=seed, palette=(accent, deep)).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Logo — only when uploaded; its corner varies with the design (not fixed).
    logo = project.get("logo_path")
    if logo and os.path.exists(logo):
        sz, rng = 150, random.Random(seed)
        corners = [(MARGIN, 70), (W - MARGIN - sz, 70), (W - MARGIN - sz, H - 70 - sz)]
        lx, ly = rng.choice(corners)
        _paste_contained(canvas, logo, (lx, ly, sz, sz))

    # Optional product cutout (upper-center negative space).
    product = project.get("product_path")
    if product and os.path.exists(product):
        _paste_contained(canvas, product, (int(W * 0.24), int(H * 0.11), int(W * 0.52), int(H * 0.34)))

    # Headline + subhead — dark text on the light field (lower third).
    headline = (project.get("headline") or project.get("target_interest") or project.get("name") or "").strip()
    if headline:
        headline = headline[0].upper() + headline[1:]
    subhead = (project.get("subhead") or "").strip()
    hf, sf = _font(74), _font(34)
    y = int(H * 0.74)
    for ln in _wrap(draw, headline, hf, W - 2 * MARGIN):
        draw.text((MARGIN, y), ln, font=hf, fill=INK)
        y += int(74 * 1.12)
    if subhead:
        draw.text((MARGIN + 2, int(H * 0.90)), _wrap(draw, subhead, sf, W - 2 * MARGIN)[0], font=sf, fill=INK)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    return out_path, seed
