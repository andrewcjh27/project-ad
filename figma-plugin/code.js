// Project AD — Ad Importer (Figma Plugin main)
// Turns an ad-spec (Ad-Spec-Schema v0.2) + hero image into EDITABLE Figma layers.
// Mapping: spec -> Figma nodes (see Figma-Handoff.md §3). Text stays editable;
// images are fills; shapes are rectangles; the logo is a placeholder ellipse
// (swap for your brand's shared component in production).

figma.showUI(__html__, { width: 360, height: 460 });

// --- Brand palette (would come from the brand package per brand_id) ----------
const PALETTES = {
  starbucks: {
    "brand:colors.primary":   { r: 0x00 / 255, g: 0x70 / 255, b: 0x4a / 255 },
    "brand:colors.secondary": { r: 0x00 / 255, g: 0x62 / 255, b: 0x41 / 255 },
    "brand:colors.cream":     { r: 0xf2 / 255, g: 0xf0 / 255, b: 0xeb / 255 },
    "brand:colors.ink":       { r: 0x14 / 255, g: 0x11 / 255, b: 0x0f / 255 },
    "brand:colors.white":     { r: 1, g: 1, b: 1 },
  },
};

function resolveColor(brandId, ref) {
  const pal = PALETTES[brandId] || PALETTES.starbucks;
  if (typeof ref === "string" && pal[ref]) return pal[ref];
  return { r: 1, g: 1, b: 1 };
}

// Brand fonts should be uploaded to your Figma org; we default to Inter so the
// plugin never fails on a missing font. Map roles -> available font.
async function loadFonts() {
  const fonts = [
    { family: "Inter", style: "Regular" },
    { family: "Inter", style: "Bold" },
  ];
  for (const fnt of fonts) {
    try { await figma.loadFontAsync(fnt); } catch (e) { /* ignore */ }
  }
}
function fontFor(role) {
  // headline/expressive -> Bold; body -> Regular. Swap to brand fonts when present.
  return role === "headline" ? { family: "Inter", style: "Bold" }
                             : { family: "Inter", style: "Regular" };
}

figma.ui.onmessage = async (msg) => {
  if (msg.type !== "build") return;
  let spec;
  try { spec = JSON.parse(msg.specJson); }
  catch (e) { figma.notify("Invalid spec JSON"); return; }

  await loadFonts();
  const brandId = spec.brand_id || "starbucks";
  const W = spec.output.width, H = spec.output.height;

  // 1) Frame = the artboard ------------------------------------------------
  const frame = figma.createFrame();
  frame.name = `Ad ${spec.ad_id || ""} · ${spec.segment_id || ""}`.trim();
  frame.resize(W, H);
  const bgRef = spec.canvas && spec.canvas.background && spec.canvas.background.value;
  frame.fills = [{ type: "SOLID", color: resolveColor(brandId, bgRef) }];

  // 2) Hero image (editable fill) -----------------------------------------
  if (msg.imageBytes) {
    const image = figma.createImage(new Uint8Array(msg.imageBytes));
    const hero = figma.createRectangle();
    hero.name = "hero-image";
    const place = spec.canvas.imagery && spec.canvas.imagery[0] && spec.canvas.imagery[0].placement;
    hero.resize(place ? place.w : W, place ? place.h : H);
    hero.x = place ? place.x : 0;
    hero.y = place ? place.y : 0;
    hero.fills = [{ type: "IMAGE", scaleMode: "FILL", imageHash: image.hash }];
    frame.appendChild(hero);
  }

  // 3) Elements (sorted by z) ---------------------------------------------
  const els = (spec.elements || []).slice().sort((a, b) => (a.z || 0) - (b.z || 0));
  for (const el of els) {
    const b = el.box || { x: 0, y: 0, w: W, h: 100 };

    if (el.type === "shape") {
      const rect = figma.createRectangle();
      rect.name = el.id || "shape";
      rect.resize(b.w, b.h); rect.x = b.x; rect.y = b.y;
      if (el.gradient) {
        const stops = el.gradient.stops.map(s => ({
          position: s.at,
          color: Object.assign({}, resolveColor(brandId, s.color), { a: s.opacity }),
        }));
        rect.fills = [{
          type: "GRADIENT_LINEAR",
          // top -> bottom
          gradientTransform: [[0, 1, 0], [-1, 0, 1]],
          gradientStops: stops,
        }];
      } else {
        const c = resolveColor(brandId, el.fill);
        rect.fills = [{ type: "SOLID", color: c, opacity: el.opacity == null ? 1 : el.opacity }];
      }
      frame.appendChild(rect);

    } else if (el.type === "text" || el.type === "legal") {
      const t = figma.createText();
      t.name = el.id || el.role || "text";
      t.fontName = fontFor(el.role);
      t.characters = el.content || el.content_ref || "";
      t.fontSize = el.size_px || 32;
      t.x = b.x; t.y = b.y;
      t.textAutoResize = "HEIGHT";
      t.resize(b.w, t.height);                 // wrap within the spec box
      t.fills = [{ type: "SOLID", color: resolveColor(brandId, el.color || "brand:colors.ink") }];
      // mark locked (manual) copy so designers know not to reword
      if (el.copy && el.copy.source === "manual") t.name += " · MANUAL (locked)";
      frame.appendChild(t);

    } else if (el.type === "logo") {
      // Placeholder roundel — replace with your brand's shared logo COMPONENT.
      const r = Math.min(b.w, b.h);
      const ell = figma.createEllipse();
      ell.name = "logo (placeholder — swap for Siren component)";
      ell.resize(r, r); ell.x = b.x; ell.y = b.y;
      ell.fills = [{ type: "SOLID", color: resolveColor(brandId, "brand:colors.primary") }];
      ell.strokes = [{ type: "SOLID", color: resolveColor(brandId, "brand:colors.cream") }];
      ell.strokeWeight = 4;
      frame.appendChild(ell);
    }
  }

  figma.currentPage.appendChild(frame);
  figma.viewport.scrollAndZoomIntoView([frame]);
  figma.notify("Ad imported as editable layers ✓");
  figma.closePlugin();
};
