"""
Project AD — Baseline Ad Renderer  (premium product-hero template)
==================================================================
Rebuilt to match the reference design language (Apple / Alure / Starbucks Royal /
2% water): the PRODUCT is the hero — large, centered, on a dramatic brand-colored
field with reflection, a thin frame, a display headline and a footer emblem.

Edit the look in the `DESIGN` block. Re-run: `python3 baseline_render.py`.

Real vs. stand-in:
  - Layout, framing, reflection, typography, footer   -> REAL (this file)
  - Product: drop a transparent PNG cutout as ./product.png (else a sample is made)
  - Fonts: drop brand fonts in ./fonts/ (display/label/body .ttf); else Lato/Lora
  - Dramatic *photographic* background: needs a real/generated image; we draw a
    rich gradient+glow+vignette+grain field as a faithful stand-in.
  - Logo: drop ./fonts/logo.png for your real mark; else a refined emblem.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
# DESIGN BASELINE — edit to restyle every ad
# ============================================================================
W, H = 1080, 1500

C = {
    "bg_center": (0x9A, 0x14, 0x12),     # royal red core
    "bg_edge":   (0x34, 0x05, 0x05),     # dark falloff
    "cream":     (0xEC, 0xE2, 0xCB),
    "gold":      (0xC9, 0xA8, 0x6A),
    "ink":       (0x16, 0x10, 0x0E),
}

COPY = {
    "headline": "Starbucks",                       # display / script
    "subhead":  "The Royal Coffee",
    "footer":   "SINCE 1971",
    "watermark": "",                               # set e.g. "ROYAL" for an Alure-style watermark
}

TYPE = {                                            # role: (font key, size, tracking)
    "headline":  ("display", 132, 0),
    "subhead":   ("display", 46, 2),
    "footer":    ("label",   30, 10),
    "watermark": ("display", 460, 0),
}

FRAME_INSET = 46
PRODUCT_PNG = os.path.join(HERE, "product.png")
PRODUCT_TARGET_H = 640
PRODUCT_CENTER = (W // 2, 800)
REFLECTION = True

# ----------------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------------
def _font_path(role):
    custom = {k: os.path.join(HERE, "fonts", f"{k}.ttf") for k in ("display", "label", "body")}[role]
    if os.path.exists(custom):
        return custom
    return {                                        # stand-ins
        "display": "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf",
        "label":   "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
        "body":    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    }[role]
def font(role, size):
    return ImageFont.truetype(_font_path(role), size)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def tracked_centered(draw, cx, y, s, fnt, fill, tracking=0):
    total = sum(draw.textlength(ch, font=fnt) + tracking for ch in s) - tracking
    x = cx - total/2
    for ch in s:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return total

def dramatic_background():
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W*0.5, H*0.46
    d = np.sqrt(((xx-cx)/(W*0.72))**2 + ((yy-cy)/(H*0.62))**2)
    t = np.clip(d, 0, 1)[..., None]
    base = np.array(C["bg_center"])*(1-t) + np.array(C["bg_edge"])*t
    # warm core glow behind the product
    g = np.clip(1 - np.sqrt(((xx-cx)/(W*0.42))**2 + ((yy-cy)/(H*0.34))**2), 0, 1)[..., None]
    base = base*(1-0.30*g) + np.array([255, 210, 170])*(0.30*g)
    base += np.random.normal(0, 4.0, base.shape)
    return Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB")

def cup_overlay():
    """Fallback product cutout (illustrated cup) if no product.png supplied."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    cx, top, bot, tw, bw = W//2, 250, 760, 150, 116
    d.polygon([(cx-tw, top), (cx+tw, top), (cx+bw, bot), (cx-bw, bot)], fill=C["cream"]+(255,))
    d.polygon([(cx+tw-26, top), (cx+tw, top), (cx+bw, bot), (cx+bw-22, bot)], fill=(0,0,0,26))
    d.rounded_rectangle([cx-tw-10, top-40, cx+tw+10, top+8], radius=14, fill=(0x3A,0x26,0x1A,255))
    d.ellipse([cx-tw-10, top-58, cx+tw+10, top-22], fill=(0x4A,0x33,0x24,255))
    sy = (top+bot)//2
    d.polygon([(cx-tw+34, sy-60),(cx+tw-34, sy-60),(cx+bw-26, sy+60),(cx-bw+26, sy+60)], fill=(0x0B,0x6B,0x46,255))
    d.ellipse([cx-34, sy-34, cx+34, sy+34], outline=C["cream"]+(255,), width=5)
    d.ellipse([cx-14, sy-14, cx+14, sy+14], fill=C["cream"]+(255,))
    return ov.crop(ov.getbbox())

def get_product():
    if os.path.exists(PRODUCT_PNG):
        return Image.open(PRODUCT_PNG).convert("RGBA")
    prod = cup_overlay(); prod.save(PRODUCT_PNG)        # write a sample to replace
    return prod

def place_product(img):
    prod = get_product(); prod = prod.crop(prod.getbbox())
    s = PRODUCT_TARGET_H / prod.height
    prod = prod.resize((max(1, int(prod.width*s)), PRODUCT_TARGET_H), Image.LANCZOS)
    cx, cy = PRODUCT_CENTER
    x, y = cx - prod.width//2, cy - prod.height//2
    base = img.convert("RGBA")

    # reflection on a glossy floor
    if REFLECTION:
        refl = prod.transpose(Image.FLIP_TOP_BOTTOM)
        grad = Image.new("L", refl.size, 0)
        for ry in range(refl.height):
            a = int(90 * (1 - ry/refl.height))
            ImageDraw.Draw(grad).line([(0, ry), (refl.width, ry)], fill=a)
        refl.putalpha(Image.composite(refl.split()[3], Image.new("L", refl.size, 0), grad))
        base.alpha_composite(refl, (x, y + prod.height - 6))

    # contact shadow / ground glow
    sh = Image.new("RGBA", base.size, (0,0,0,0))
    ImageDraw.Draw(sh).ellipse([cx-prod.width*0.55, y+prod.height-34,
                                cx+prod.width*0.55, y+prod.height+54], fill=(0,0,0,150))
    base = Image.alpha_composite(base, sh.filter(ImageFilter.GaussianBlur(30)))
    base.alpha_composite(prod, (x, y))
    return base

def emblem(draw, cx, cy, r):
    logo = os.path.join(HERE, "fonts", "logo.png")
    if os.path.exists(logo): return False
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C["gold"]+(255,), width=3)
    draw.ellipse([cx-r+8, cy-r+8, cx+r-8, cy+r-8], outline=C["gold"]+(140,), width=2)
    f = font("display", int(r*1.1)); w = draw.textlength("S", font=f)
    draw.text((cx-w/2, cy-r*0.72), "S", font=f, fill=C["gold"]+(255,))
    return True

# ============================================================================
# Compose
# ============================================================================
def render(out_path="sbux_psl_ad.png"):
    img = dramatic_background()

    # optional big watermark behind product
    if COPY["watermark"]:
        wm = Image.new("RGBA", (W, H), (0,0,0,0)); wd = ImageDraw.Draw(wm)
        fk, sz, tr = TYPE["watermark"]; f = font(fk, sz)
        tw = wd.textlength(COPY["watermark"], font=f)
        wd.text((W/2 - tw/2, H*0.30), COPY["watermark"], font=f, fill=C["cream"]+(26,))
        img = Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")

    img = place_product(img)
    draw = ImageDraw.Draw(img, "RGBA")

    # thin frame
    draw.rectangle([FRAME_INSET, FRAME_INSET, W-FRAME_INSET, H-FRAME_INSET],
                   outline=C["cream"]+(150,), width=2)

    # headline + subhead (top, centered)
    fk, sz, tr = TYPE["headline"]; f = font(fk, sz)
    hw = draw.textlength(COPY["headline"], font=f)
    draw.text((W/2 - hw/2, 96), COPY["headline"], font=f, fill=C["cream"]+(255,))
    fk, sz, tr = TYPE["subhead"]; f = font(fk, sz)
    tracked_centered(draw, W/2, 250, COPY["subhead"], f, C["gold"]+(255,), tr)

    # footer: side rules + emblem + since-line
    fy = H - 150
    er = 34; emblem(draw, W/2, fy, er)
    logo = os.path.join(HERE, "fonts", "logo.png")
    if os.path.exists(logo):
        lg = Image.open(logo).convert("RGBA").resize((er*2, er*2)); img.alpha_composite(lg, (W//2-er, fy-er))
    fk, sz, tr = TYPE["footer"]; f = font(fk, sz)
    tw = sum(draw.textlength(ch, font=f)+tr for ch in COPY["footer"]) - tr
    ty = fy + er + 26
    tracked_centered(draw, W/2, ty, COPY["footer"], f, C["cream"]+(230,), tr)
    rule_y = ty + sz/2
    draw.line([(FRAME_INSET+70, rule_y), (W/2 - tw/2 - 26, rule_y)], fill=C["cream"]+(120,), width=2)
    draw.line([(W/2 + tw/2 + 26, rule_y), (W-FRAME_INSET-70, rule_y)], fill=C["cream"]+(120,), width=2)

    img.convert("RGB").save(out_path)
    print("Rendered", out_path)

if __name__ == "__main__":
    np.random.seed(7)
    render()
