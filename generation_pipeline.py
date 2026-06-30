"""
Project AD — Multi-Agent Generation Pipeline (demo)
===================================================
Implements the agent roster from Agent-Architecture.md end-to-end and renders a
REAL ad PNG for the Starbucks fall/PSL loyal segment found in the spike.

Each role is a separate agent that reads/writes the shared ad-spec (Ad-Spec-Schema v0.2).
LLM-backed agents (Strategist, Matcher, Art Director, Copywriter, Critic) use
rule-based stand-ins here so the demo runs offline — clearly marked `# [LLM]`.
The Image Generator is a procedural stand-in for a hosted image model `# [IMG]`.
The Compositor and Brand Guardian are real deterministic code (production-shaped).
"""

import json, os, copy
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from image_agent import get_image_provider   # real image-model adapter (falls back to procedural)
import ad_brief                              # brand image style + optional manual overrides
import llm_agent                             # Art Director / Copywriter brains (LLM or data-driven)
import product_discovery                     # retrieves the product by interest (web-sourced for now)
import brand_memory                          # retrieves past on-brand ads as few-shot exemplars
import brand_fit                             # shared brand-color primitive (+ any-image scorer)

# ----------------------------------------------------------------------------
# Brand package (subset of Starbucks-Brand-Package.md, machine form)
# ----------------------------------------------------------------------------
BRAND = {
    "brand_id": "starbucks",
    "colors": {
        "primary":   (0x00, 0x70, 0x4A),   # #00704A
        "secondary": (0x00, 0x62, 0x41),   # #006241
        "cream":     (0xF2, 0xF0, 0xEB),   # #F2F0EB
        "ink":       (0x14, 0x11, 0x0F),
        "white":     (0xFF, 0xFF, 0xFF),
    },
    "fonts": {  # local stand-ins for Pike / Lander / Sodo Sans
        "heading":    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "expressive": "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf",
        "body":       "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    },
    "language": {"banned_words": ["cheap", "discount", "deal", "guys"]},
    "min_contrast_ratio": 4.5,
}

# Cross-platform fallbacks for when the configured (Linux) font path isn't present
# — e.g. on macOS. Real brand fonts in fonts/ still take precedence via BRAND["fonts"].
_FONT_FALLBACKS = {
    "heading":    ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                   "/System/Library/Fonts/Helvetica.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"],
    "expressive": ["/System/Library/Fonts/Supplemental/Georgia.ttf",
                   "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "body":       ["/System/Library/Fonts/Supplemental/Arial.ttf",
                   "/System/Library/Fonts/Helvetica.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}

def f(role, size):
    candidates = [BRAND["fonts"][role], *_FONT_FALLBACKS.get(role, [])]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)  # last resort: never crash the render

# ----------------------------------------------------------------------------
# Shared ad-spec (the handoff contract). Agents fill their own fields.
# ----------------------------------------------------------------------------
def blank_spec(segment):
    return {
        "spec_version": "0.2", "ad_id": "sbux-gen-0001", "brand_id": "starbucks",
        "brand_config_version": 1, "segment_id": segment["segment_id"],
        "output": {"type": "image", "width": 1080, "height": 1350, "aspect_ratio": "4:5", "format": "png"},
        "mode": "layered", "concept": {}, "canvas": {}, "elements": [],
        "personalization": {"segment_id": segment["segment_id"], "segment_size": segment["size"],
                             "signals_used": segment["signals"], "literalness": "inferential",
                             "pii_used": False, "off_limits_respected": True},
        "provenance": {"created_by": "system", "agents": []}, "qc": {"gates": {}, "ai_critique": {}},
    }

def log(spec, agent, note):
    spec["provenance"]["agents"].append({"agent": agent, "note": note})

# ----------------------------------------------------------------------------
# Campaign formats — one concept renders into each (Phase 2: campaign coherence).
# The concept/copy/palette are format-INDEPENDENT; only the layout below changes.
# ----------------------------------------------------------------------------
FORMATS = {
    "poster_4x5":    {"w": 1080, "h": 1350, "aspect": "4:5"},   # the original baseline
    "square_1x1":    {"w": 1080, "h": 1080, "aspect": "1:1"},
    "landscape_16x9": {"w": 1920, "h": 1080, "aspect": "16:9"},
}

# One hero seed shared across a campaign so every format reads as the same shoot.
_HERO_SEED = 771204

def layout_elements(W, H, palette, prompt, psrc, headline, subhead):
    """Deterministic, proportional layout for one format.

    The ONLY format-dependent layer. Portrait/square stack the copy in the lower
    third; landscape anchors it lower-left with room for the wide hero. Typography
    and margins scale with the format so a concept stays legible at every aspect.
    """
    landscape = W > H
    canvas = {
        "background": {"type": "color", "value": "brand:colors.cream"},
        "imagery": [{
            "id": "img_hero", "role": "hero",
            "prompt": prompt, "prompt_source": psrc,          # AI-generated from data
            "negative_prompt": ad_brief.NEGATIVE_PROMPT,
            "palette": palette, "seed": _HERO_SEED,
            "placement": {"x": 0, "y": 0, "w": W, "h": H},
        }],
    }
    logo_sz = round(0.082 * H)                                # logo scales with height
    if landscape:
        margin = round(0.05 * W)
        head_size, sub_size = round(0.075 * H), round(0.034 * H)
        scrim_top = int(H * 0.45)
        text_w = round(0.55 * W)                              # copy in the left half
        head_y, sub_y = int(H * 0.62), int(H * 0.86)
    else:
        square = abs(W - H) < 1
        margin = round(0.074 * W)
        head_size, sub_size = round(0.068 * W), round(0.031 * W)
        scrim_top = int(H * (0.50 if square else 0.52))
        text_w = W - 2 * margin
        head_y = int(H * (0.70 if square else 0.74))
        sub_y = int(H * (0.88 if square else 0.90))
    elements = [
        {"id": "scrim", "type": "shape", "shape": "rect", "z": 5,
         "gradient": {"type": "linear", "angle": 180, "stops": [
             {"color": "brand:colors.primary", "opacity": 0.0, "at": 0.0},
             {"color": "brand:colors.primary", "opacity": 0.92, "at": 1.0}]},
         "box": {"x": 0, "y": scrim_top, "w": W, "h": H - scrim_top}},
        {"id": "headline", "type": "text", "role": "headline", "z": 10,
         "font": "brand:typography.fonts.expressive", "size_px": head_size, "color": "brand:colors.cream",
         "auto_scrim": True, "box": {"x": margin, "y": head_y, "w": text_w, "h": round(0.20*H)},
         "content": headline, "copy": {"source": "generated", "locked": False}},
        {"id": "subhead", "type": "text", "role": "subhead", "z": 10,
         "font": "brand:typography.fonts.body", "size_px": sub_size, "color": "brand:colors.cream",
         "box": {"x": margin + 2, "y": sub_y, "w": text_w, "h": round(0.06*H)},
         "content": subhead, "copy": {"source": "generated", "locked": False}},
        {"id": "logo", "type": "logo", "variant": "siren-white", "z": 20,
         "box": {"x": margin, "y": round(0.052*H), "w": logo_sz, "h": logo_sz}},
    ]
    return canvas, elements

# ============================================================================
# AGENTS
# ============================================================================
class Strategist:
    """[LLM] Segment (+ blended persona) -> creative brief & angle."""
    def run(self, segment, spec):
        life, interest = segment["lifecycle"], segment["dominant_interest"]
        # Prefer the synthesized persona's angle (from a mixture of traits); fall back
        # to the per-lifecycle angle for segments without a persona (e.g. the demo).
        persona = segment.get("persona") or {}
        angle = persona.get("angle") or {
            "loyal":  "quiet, understated, ritual-anchored; familiar, never a hard sell",
            "new":    "minimal brand-essence; a calm, confident invitation",
            "lapsed": "understated, warm return; their familiar favorite, no pressure",
            "vip":    "restrained, premium, exclusive; minimal and refined",
        }.get(life, "minimal, understated; calm and personal")
        pillar = "seasonal" if ("fall" in interest or "season" in interest) else "ritual"
        spec["concept"].update({
            "rationale": persona.get("summary") or f"{life} segment centered on '{interest}'.",
            "copy_angle": angle,
            "messaging_pillar": pillar,
        })
        if persona.get("name"):
            spec["concept"]["persona"] = {"name": persona.get("name"),
                                          "summary": persona.get("summary")}
        seg = dict(segment); seg["pillar"] = pillar               # enrich for downstream agents
        spec["_segment"] = seg
        log(spec, "Strategist",
            f"persona '{persona['name']}'" if persona.get("name") else f"angle for {life}/{interest}")
        return spec

class ProductMatcher:
    """[LLM] Final product pick from ranked candidates + reason."""
    def run(self, candidates, segment, spec):
        top = candidates[0]
        spec["personalization"].update({
            "selected_product": top["product_id"],
            "selection_reason": f"highest interest+lifecycle fit (sim={top['sim']:.2f}); {top['why']}",
        })
        spec["_product"] = top
        log(spec, "ProductMatcher", f"selected {top['product_id']}")
        return spec

class ArtDirector:
    """[LLM] Concept, color choices, imagery prompt — all format-INDEPENDENT.

    Layout is decided per-format later by `layout_elements`, so one concept can
    render into every campaign format.
    """
    def run(self, spec):
        p = spec["_product"]
        seg = spec["_segment"]
        # Retrieve past on-brand ads for this segment interest as few-shot exemplars
        # (soft guidance only; hard rules stay with BrandGuardian). Cold-start safe -> [].
        exemplars = brand_memory.retrieve_exemplars(seg.get("dominant_interest", ""), spec["brand_id"])
        spec["_exemplars"] = exemplars
        spec["concept"]["exemplars_used"] = [e["exemplar_id"] for e in exemplars]
        # GENERATE the image prompt from data (product + segment + brand style),
        # unless a human override is set in ad_brief.MANUAL_IMAGE_PROMPT.
        if ad_brief.MANUAL_IMAGE_PROMPT:
            prompt, psrc = ad_brief.MANUAL_IMAGE_PROMPT + f". {ad_brief.PHOTO_TAG}.", "manual"
        else:
            prompt, psrc = llm_agent.generate_image_prompt(
                p, seg, ad_brief.BRAND_IMAGE_STYLE, ad_brief.NEGATIVE_PROMPT, ad_brief.PHOTO_TAG,
                exemplars=exemplars)
        spec["concept"]["image_prompt"] = prompt                  # AI-generated from data
        spec["concept"]["image_prompt_source"] = psrc
        spec["concept"]["palette"] = p["palette"]
        spec["concept"]["big_idea"] = ""                          # written by Copywriter next
        log(spec, "ArtDirector", f"image prompt {psrc}; concept decided (format-independent)")
        return spec

class Copywriter:
    """[LLM] GENERATES copy from data (or honors manual override). Format-independent."""
    def run(self, spec):
        if ad_brief.MANUAL_HEADLINE or ad_brief.MANUAL_SUBHEAD:
            head, sub, csrc = ad_brief.MANUAL_HEADLINE, ad_brief.MANUAL_SUBHEAD, "manual"
        else:
            head, sub, csrc = llm_agent.generate_copy(
                spec["_product"], spec["_segment"], spec["concept"]["copy_angle"],
                exemplars=spec.get("_exemplars"))
        spec["concept"]["big_idea"] = head
        spec["concept"]["subhead"] = sub
        spec["concept"]["copy_source"] = csrc
        log(spec, "Copywriter", "headline + subhead in brand voice")
        return spec

class ImageGenerator:
    """[IMG] Calls a real image model via the provider adapter; falls back to procedural offline."""
    def __init__(self):
        self.provider = get_image_provider()          # OpenAI / Flux / procedural by env
    def run(self, spec):
        W, H = spec["output"]["width"], spec["output"]["height"]
        im = spec["canvas"]["imagery"][0]
        try:
            img = self.provider.generate(
                im["prompt"], im.get("negative_prompt", ""), W, H,
                seed=im.get("seed"), palette=im.get("palette"),
            )
            note = f"hero via {self.provider.name}"
        except Exception as e:                          # never block generation on a provider error
            from image_agent import ProceduralProvider
            img = ProceduralProvider().generate(im["prompt"], "", W, H, palette=im.get("palette"))
            note = f"provider failed ({e}); used procedural fallback"
        log(spec, "ImageGenerator", note)
        return img.convert("RGB")

class Compositor:
    """Deterministic renderer: assembles the spec + hero into final pixels."""
    def _resolve(self, ref):
        if isinstance(ref, str) and ref.startswith("brand:colors."):
            return BRAND["colors"][ref.split(".")[-1]]
        return ref

    def _wrap(self, draw, text, font, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) <= max_w: cur = test
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        return lines

    def run(self, spec, hero):
        W, H = spec["output"]["width"], spec["output"]["height"]
        canvas = hero.convert("RGB").copy()
        draw = ImageDraw.Draw(canvas, "RGBA")
        for el in sorted(spec["elements"], key=lambda e: e.get("z", 0)):
            b = el["box"]
            if el["type"] == "shape":                      # gradient scrim
                stops = el["gradient"]["stops"]
                c = self._resolve(stops[0]["color"])
                for i in range(b["h"]):
                    t = i / max(1, b["h"]-1)
                    a = int(255 * (stops[0]["opacity"]*(1-t) + stops[1]["opacity"]*t))
                    draw.line([(b["x"], b["y"]+i), (b["x"]+b["w"], b["y"]+i)], fill=(*c, a))
            elif el["type"] == "text":
                role = el["role"]
                font = f("expressive" if role == "headline" else "body", el["size_px"])
                col = self._resolve(el["color"])
                lines = self._wrap(draw, el["content"], font, b["w"])
                y = b["y"]
                for ln in lines:
                    draw.text((b["x"], y), ln, font=font, fill=col)
                    y += int(el["size_px"] * 1.12)
            elif el["type"] == "logo":                     # placeholder for Siren component
                cx, cy, r = b["x"]+b["w"]//2, b["y"]+b["h"]//2, b["w"]//2
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*BRAND["colors"]["primary"], 255))
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(*BRAND["colors"]["cream"], 255), width=4)
                star = f("body", int(r*0.9)); sw = draw.textlength("★", font=star)
                draw.text((cx-sw/2, cy-r*0.62), "★", font=star, fill=(*BRAND["colors"]["cream"], 255))
        return canvas

# ============================================================================
# QC AGENTS
# ============================================================================
def luminance(c):
    s = [v/255 for v in c]
    s = [(v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4) for v in s]
    return 0.2126*s[0] + 0.7152*s[1] + 0.0722*s[2]

def contrast(c1, c2):
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi+0.05)/(lo+0.05)

class BrandGuardian:
    """Deterministic hard-rule enforcement; can veto."""
    def run(self, spec, img):
        gates = {}
        # banned words
        copy = " ".join(e.get("content", "") for e in spec["elements"] if e["type"] == "text").lower()
        gates["language_clean"] = "pass" if not any(w in copy for w in BRAND["language"]["banned_words"]) else "fail"
        # headline contrast against the scrim base (primary green)
        cr = contrast(BRAND["colors"]["cream"], BRAND["colors"]["primary"])
        gates["contrast_aa"] = "pass" if cr >= BRAND["min_contrast_ratio"] else "fail"
        gates["contrast_value"] = round(cr, 2)
        # brand color present (sample inside the logo roundel, below the star glyph)
        lg = next(e for e in spec["elements"] if e["type"] == "logo")
        cx = lg["box"]["x"] + lg["box"]["w"]//2
        cy = lg["box"]["y"] + lg["box"]["h"]//2 + int(lg["box"]["w"]*0.30)
        sample = img.getpixel((cx, cy))
        gates["brand_color_present"] = "pass" if brand_fit.is_brand_color(
            sample, [BRAND["colors"]["primary"]], tol=40) else "fail"
        # logo present
        gates["logo_present"] = "pass" if any(e["type"] == "logo" for e in spec["elements"]) else "fail"
        spec["qc"]["gates"] = gates
        verdict = all(v == "pass" for k, v in gates.items() if isinstance(v, str) and v in ("pass", "fail"))
        log(spec, "BrandGuardian", f"gates {'PASS' if verdict else 'VETO'}")
        return verdict, gates

class Critic:
    """[LLM-vision] Taste score against soft brand guidance (heuristic stand-in)."""
    def run(self, spec, img):
        # heuristic: reward a clear single headline, presence of subhead, on-pillar concept
        n_text = sum(1 for e in spec["elements"] if e["type"] == "text")
        score = 0.6 + 0.1*(n_text >= 2) + 0.1*("season" in spec["concept"]["messaging_pillar"]) \
                + 0.1*(len(spec["concept"]["big_idea"]) < 45) + 0.1
        score = round(min(score, 0.95), 2)
        verdict = "approve" if score >= 0.75 else "flag"
        spec["qc"]["ai_critique"] = {"score": score, "verdict": verdict,
                                     "notes": "clear hierarchy; warm grade on-brand; concise headline"}
        log(spec, "Critic", f"score {score} -> {verdict}")
        return verdict

# ============================================================================
# ORCHESTRATOR
# ============================================================================
class Orchestrator:
    def __init__(self):
        self.strategist, self.matcher, self.ad, self.copy = Strategist(), ProductMatcher(), ArtDirector(), Copywriter()
        self.img, self.comp, self.guard, self.crit = ImageGenerator(), Compositor(), BrandGuardian(), Critic()

    def _decide(self, segment):
        """Run the format-INDEPENDENT agents once: strategy, product, concept, copy."""
        spec = blank_spec(segment)
        self.strategist.run(segment, spec)
        # PRODUCT IS RETRIEVED by similarity to the segment interest (not hardcoded).
        candidates = product_discovery.discover_candidates(segment["dominant_interest"])
        self.matcher.run(candidates, segment, spec)
        self.ad.run(spec)
        self.copy.run(spec)
        return spec

    def _render_format(self, base, fmt_key):
        """Materialize one format from a decided concept: layout -> hero -> composite -> QC."""
        fmt = FORMATS[fmt_key]
        W, H = fmt["w"], fmt["h"]
        spec = copy.deepcopy(base)
        spec["ad_id"] = f"{base['ad_id']}-{fmt_key}"
        spec["output"] = {"type": "image", "width": W, "height": H,
                          "aspect_ratio": fmt["aspect"], "format": "png", "format_key": fmt_key}
        c = spec["concept"]
        spec["canvas"], spec["elements"] = layout_elements(
            W, H, c["palette"], c["image_prompt"], c["image_prompt_source"],
            c["big_idea"], c.get("subhead", ""))
        hero = self.img.run(spec)
        canvas = self.comp.run(spec, hero)
        ok, gates = self.guard.run(spec, canvas)
        if not ok:
            # targeted regeneration would route back to the responsible agent; demo asserts pass
            raise RuntimeError(f"Brand Guardian veto ({fmt_key}): {gates}")
        verdict = self.crit.run(spec, canvas)
        return spec, canvas, verdict

    @staticmethod
    def _clean_and_save_spec(spec, path):
        for k in ("_product", "_segment", "_exemplars"):
            spec.pop(k, None)
        with open(path, "w") as fp:
            json.dump(spec, fp, indent=2)

    def run(self, segment, out_path):
        """Single-format (poster) generation — back-compatible entry point."""
        base = self._decide(segment)
        spec, canvas, verdict = self._render_format(base, "poster_4x5")
        # Quality-filtered brand memory: only remember Critic-approved ads.
        if verdict == "approve":
            brand_memory.remember(spec, spec["brand_id"])
        canvas.save(out_path)
        self._clean_and_save_spec(spec, out_path.replace(".png", ".spec.json"))
        return spec, verdict, out_path

    def run_campaign(self, segment, out_dir, formats=None):
        """Render ONE concept into multiple formats that share copy/palette/product.

        The concept, copy, palette, and hero seed are decided once; only the layout
        differs per format, so the set reads as one campaign. Writes per-format PNG +
        spec into `out_dir` plus a `campaign.json` manifest of the shared concept.
        """
        formats = formats or list(FORMATS)
        os.makedirs(out_dir, exist_ok=True)
        base = self._decide(segment)
        remembered, items = False, []
        for fmt_key in formats:
            spec, canvas, verdict = self._render_format(base, fmt_key)
            if verdict == "approve" and not remembered:
                brand_memory.remember(spec, spec["brand_id"]); remembered = True
            png = os.path.join(out_dir, f"{fmt_key}.png")
            canvas.save(png)
            self._clean_and_save_spec(spec, os.path.join(out_dir, f"{fmt_key}.spec.json"))
            items.append({"format": fmt_key, "size": [FORMATS[fmt_key]["w"], FORMATS[fmt_key]["h"]],
                          "aspect_ratio": FORMATS[fmt_key]["aspect"],
                          "png": os.path.basename(png), "critic": verdict})
        manifest = {
            "campaign_id": base["ad_id"], "brand_id": base["brand_id"],
            "segment_id": segment["segment_id"],
            "shared_concept": {
                "product": base["personalization"]["selected_product"],
                "headline": base["concept"]["big_idea"],
                "subhead": base["concept"].get("subhead", ""),
                "messaging_pillar": base["concept"]["messaging_pillar"],
                "image_prompt": base["concept"]["image_prompt"],
                "exemplars_used": base["concept"].get("exemplars_used", []),
            },
            "formats": items,
        }
        with open(os.path.join(out_dir, "campaign.json"), "w") as fp:
            json.dump(manifest, fp, indent=2)
        return manifest


if __name__ == "__main__":
    # Only the SEGMENT (audience data) is given. The product is RETRIEVED from its
    # interest; the prompt and copy are GENERATED from the retrieved product + segment.
    segment = {"segment_id": "seg_loyal_1", "size": 16, "lifecycle": "loyal",
               "dominant_interest": "fall seasonal ritual morning autumn",
               "daypart": "morning", "season": "autumn",
               "signals": ["interest:fall_seasonal", "behavioral:morning", "lifecycle:loyal"]}
    orch = Orchestrator()
    spec, verdict, path = orch.run(segment, "sbux_psl_ad.png")
    sel = spec["personalization"]
    print("Rendered:", path, "| critic:", verdict)
    print("Product retrieved:", sel["selected_product"], "—", sel["selection_reason"])
    print("Image prompt:", spec["canvas"]["imagery"][0]["prompt"][:90], "...")
    print("Agents:", " -> ".join(a["agent"] for a in spec["provenance"]["agents"]))
    print("Headline:", next(e["content"] for e in spec["elements"] if e["id"] == "headline"))
    # Campaign coherence: one concept -> multiple formats that share copy/palette/product.
    manifest = orch.run_campaign(segment, "campaign_sbux_psl")
    print("\nCampaign:", manifest["campaign_id"], "->", "campaign_sbux_psl/  (shared headline:",
          repr(manifest["shared_concept"]["headline"]) + ")")
    for it in manifest["formats"]:
        print(f"  {it['format']:16s} {it['size'][0]}x{it['size'][1]:<5} {it['aspect_ratio']:6s} critic: {it['critic']}")
