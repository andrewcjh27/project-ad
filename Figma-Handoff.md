# Figma Handoff — Editable Design Export

*How a generated ad lands in Figma as **editable layers** so a designer can do final retouch before it ships. This is a natural payoff of the layered ad-spec: we never flatten to a PNG and ask the designer to start over — we hand them the actual layers.*

Status: Draft · Pairs with `Ad-Spec-Schema.md` (v0.2), `Project-AD-Planning.md`

---

## 1. Why this fits the architecture

The ad spec already describes an ad as separable layers — imagery, text, logo, shapes, legal — each with position, font, and color. That is essentially a Figma layer tree. So the handoff is a **direct mapping** from spec → Figma nodes, producing fully editable text, repositionable elements, and swappable images. The designer retouches in their native tool; nothing is re-traced.

This also strengthens the **human-in-the-loop quality gate**: the review console's "needs retouch" path becomes "Open in Figma," where the reviewer-designer fixes the last 5% and exports the final.

---

## 2. The right technical path: a Figma plugin (not REST)

Figma's two APIs differ critically on **write**:

| | Plugin API | REST API |
|---|---|---|
| Read file content | ✅ | ✅ |
| **Create / modify layers** | ✅ | ❌ **read-only for content** |
| Where it runs | Inside Figma (sandboxed) | External HTTP |

**Conclusion:** creating editable layers from our spec requires the **Plugin API**. The REST API cannot write design content. So we build a small **Project AD Figma plugin** that:

1. Pulls a generated ad spec (by `ad_id`) from our backend.
2. Constructs the corresponding Figma nodes via the Plugin API.
3. Loads the brand fonts (`loadFontAsync`) so text renders correctly and stays editable.
4. Drops the assembled, named, editable frame into the designer's canvas.

> REST API still has a role: the plugin (or our backend) can use REST to *read back* the finished Figma file and export the final asset once the designer is done.

---

## 3. Spec → Figma node mapping

| Ad-spec element | Figma node | Editability for designer |
|---|---|---|
| `output` (w/h) | `FrameNode` sized to the ad | Frame = the artboard |
| `canvas.background` | Frame fill / bottom `RectangleNode` | Recolor |
| `canvas.imagery[]` | `RectangleNode` with image fill (or placed image) | Swap/replace, reposition, mask, adjust |
| `elements[type:text]` | `TextNode` (real brand font, real copy) | **Fully editable text** — reword, resize, restyle |
| `elements[type:logo]` | Logo `ComponentNode`/instance from a shared library | Swap variant, reposition (locked aspect) |
| `elements[type:shape]` | `RectangleNode` (+ gradient/opacity for scrims) | Adjust scrim, color, opacity |
| `elements[type:legal]` | `TextNode`, small | Edit if permitted |
| `box {x,y,w,h}` | Node x/y/width/height | Drag/resize |
| `z` | Layer order | Reorder |

The plugin names every layer from the spec (`headline`, `hero-image`, `siren-logo`) so the file is clean and navigable, not a dump of `Rectangle 47`.

---

## 4. Fonts & brand assets

- The brand's real fonts (e.g. Starbucks' Sodo Sans / Lander / Pike) must be **available in the Figma org** (uploaded as shared fonts) so the plugin's `loadFontAsync` succeeds and text matches the render exactly. This ties to brand-asset management — fonts live with the brand package.
- The logo should be a **shared Figma component/library asset** per brand, so the plugin instances it (preserving integrity and clear-space) rather than pasting a raw file.
- Brand colors map cleanly to **Figma color styles/variables** per brand — so designer edits stay on-palette and the `brand:colors.*` references round-trip.

---

## 5. Flow (one-way for v1)

```
 generated ad spec ──▶ Project AD Figma plugin ──▶ editable frame on canvas
                                                        │
                                              designer retouches (final 5%)
                                                        │
                                                  export final asset
                                                        │
                            (optional) read back via REST ──▶ store as the shipped version
```

**One-way for v1** (spec → Figma → export). We do **not** try to sync designer edits back into the spec automatically — round-tripping arbitrary manual edits into a structured spec is hard and error-prone. Instead, the Figma-exported asset becomes the final shipped version, and we log that a human retouched it (feeds the quality loop: which segments/templates needed manual fixes → improve them).

> Future option: capture *structured* designer changes (text edits, repositions) back into the spec for learning. Deferred — not needed to ship.

---

## 6. Where it sits in the product

- **Default path:** auto-QC → AI critique → (most ads) approve and ship without Figma.
- **Retouch path:** reviewer flags "needs polish" → **Open in Figma** → designer finalizes → export. Only the ads that need it go to Figma, keeping designer load proportional to segment volume, not user volume.
- This keeps the agency-quality bar: a human designer can always take the last step in their professional tool.

---

## 7. Build notes / spike
- Minimal plugin first: read one spec JSON (paste or fetch), build a frame with one image fill + one text node in a brand font + the logo component. Prove the mapping and font loading.
- Confirm brand fonts upload to the Figma org and `loadFontAsync` resolves them.
- Decide logo delivery: shared library component vs. embedded SVG.
- **Fallback if plugin work slips:** export the spec as **SVG** and import into Figma. Quicker, but text editability and font fidelity are weaker and images embed — acceptable as a stopgap, not the target.
- Scope: static **image + poster** only for now (video handoff is a separate, later problem).

---

## Sources
- [Figma — Compare the APIs (Plugin can write, REST is read-only for content)](https://developers.figma.com/compare-apis/)
- [Figma Plugin API — Introduction](https://developers.figma.com/docs/plugins/)
- [Figma Plugin API — Working with Text (`loadFontAsync`)](https://www.figma.com/plugin-docs/working-with-text/)
- [Figma Plugin API — TextNode](https://www.figma.com/plugin-docs/api/TextNode/)
