"""
Make Product PNG — render a clean transparent-background product cutout.
========================================================================
Produces ./product.png (a takeaway coffee cup) ready to insert into the ad.
This is a *rendered* cutout (no copyrighted photo, no image model needed).
Drop in your own product.png to replace it; the logo roundel is kept generic.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WC = {
    "cream":  (244, 240, 232),
    "cream_d":(214, 208, 196),
    "green":  (0, 0x6B, 0x46),
    "green_d":(0, 0x4B, 0x31),
    "lid":    (54, 38, 28),
    "lid_hi": (92, 68, 50),
}
Wd, Hd = 720, 1040

def hgrad(w, h, left, right):
    xs = np.linspace(0, 1, w)[None, :]
    arr = np.zeros((h, w, 4), "uint8")
    for i in range(4):                       # keep alpha from the gradient (channel 3)
        arr[..., i] = (left[i]*(1-xs) + right[i]*xs).astype("uint8")
    return Image.fromarray(arr, "RGBA")

def vgrad(w, h, top, bot):
    ys = np.linspace(0, 1, h)[:, None]
    arr = np.zeros((h, w, 4), "uint8")
    for i in range(4):
        arr[..., i] = (top[i]*(1-ys) + bot[i]*ys).astype("uint8")
    return Image.fromarray(arr, "RGBA")

def render(path="product.png"):
    img = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = Wd//2
    top, bot, tw, bw = 175, 905, 168, 132          # cup body extents / half-widths

    # --- cup body (cream) with rounded base ---
    body = [(cx-tw, top), (cx+tw, top), (cx+bw, bot-12), (cx-bw, bot-12)]
    d.polygon(body, fill=WC["cream"]+(255,))
    d.ellipse([cx-bw, bot-40, cx+bw, bot+14], fill=WC["cream"]+(255,))

    # --- cylindrical shading: dark edges, light centre-left highlight ---
    shade = hgrad(Wd, Hd, (0, 0, 0, 70), (0, 0, 0, 0))     # dark left
    shade2 = hgrad(Wd, Hd, (0, 0, 0, 0), (0, 0, 0, 90))    # dark right
    mask = Image.new("L", (Wd, Hd), 0)
    ImageDraw.Draw(mask).polygon(body, fill=255)
    ImageDraw.Draw(mask).ellipse([cx-bw, bot-40, cx+bw, bot+14], fill=255)
    img = Image.composite(Image.alpha_composite(img, shade), img, mask.point(lambda v: v//3))
    img = Image.composite(Image.alpha_composite(img, shade2), img, mask)
    d = ImageDraw.Draw(img)
    # soft specular highlight stripe (left third)
    hl = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([cx-tw+26, top+20, cx-tw+96, bot-60], fill=(255, 255, 255, 70))
    img = Image.alpha_composite(img, hl.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(img)

    # --- green sleeve (tapered band) with vertical gradient + roundel ---
    sy0, sy1 = 470, 690
    sl_tw = tw - int((sy0-top)/(bot-top)*(tw-bw))
    sl_bw = tw - int((sy1-top)/(bot-top)*(tw-bw))
    sleeve_poly = [(cx-sl_tw+6, sy0), (cx+sl_tw-6, sy0), (cx+sl_bw-6, sy1), (cx-sl_bw+6, sy1)]
    smask = Image.new("L", (Wd, Hd), 0); ImageDraw.Draw(smask).polygon(sleeve_poly, fill=255)
    sg = vgrad(Wd, Hd, WC["green"]+(255,), WC["green_d"]+(255,))
    img = Image.composite(sg, img, smask)
    d = ImageDraw.Draw(img)
    # roundel (generic — swap for the real logo if desired)
    ry = (sy0+sy1)//2
    d.ellipse([cx-52, ry-52, cx+52, ry+52], fill=WC["green_d"]+(255,), outline=WC["cream"]+(255,), width=6)
    d.ellipse([cx-22, ry-22, cx+22, ry+22], outline=WC["cream"]+(255,), width=4)
    d.ellipse([cx-7, ry-7, cx+7, ry+7], fill=WC["cream"]+(255,))

    # --- lid ---
    d.rounded_rectangle([cx-tw-12, top-46, cx+tw+12, top+10], radius=16, fill=WC["lid"]+(255,))
    d.ellipse([cx-tw-12, top-70, cx+tw+12, top-24], fill=WC["lid_hi"]+(255,))
    d.ellipse([cx-tw-12, top-66, cx+tw+12, top-30], fill=WC["lid"]+(255,))
    d.rounded_rectangle([cx-tw-18, top+4, cx+tw+18, top+22], radius=8, fill=WC["lid"]+(255,))  # rim

    out = img.crop(img.getbbox())
    try:
        out.save(path)
    except PermissionError:
        path = "product_cup.png"; out.save(path)
    print("Saved", path, out.size)
    return path

if __name__ == "__main__":
    render()
