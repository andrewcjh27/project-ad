# Reference ads — house minimal style

These are the reference ads that define the minimal aesthetic **PRO-AD** aims for.
Their shared design language is now baked into the default background prompt
(`ad-studio.html` → `bgPrompt`, and `webapp/generator.py`), so new ads lean
minimal by default. To match a *specific* reference's look on a project, upload
it on **Step 3 · References** in the studio (style only — never copied).

## The references (palettes from the built-in analyzer)

| File | Brand ad | Palette | Analyzer read |
|------|----------|---------|----------------|
| `apple-beyond-innovation.jpg` | Apple, "Beyond Innovation" | `#040202 #38221C #8F6855 #D9CAC2` | minimal & flat · dark · neutral · low-contrast |
| `alure-skincare.png` | Alure skincare | `#374D28 #6E7C58 #CFDEBA #A6B38E` | minimal & flat · mid-toned · warm · balanced |
| `lotte-2percent.png` | Lotte 2% | `#83AEDA #CCDAEB #C98F78 #668454` | minimal & flat · light · cool · low-contrast |
| `starbucks-royal-coffee.png` | Starbucks, "The Royal Coffee" | `#8C2620 #561915 #9C6659 #D5BDAC` | moderately detailed · dark · warm · low-contrast |

Each ad exemplifies a different mood — dark/cinematic (Apple), natural/editorial
(Alure), fresh/airy (Lotte), rich/dramatic (Starbucks) — but they share one clear
design language.

## Shared minimal-design DNA (encoded into the default prompt)

- **Monochromatic** — each ad commits to a *single hue family* with 2–3 tones
  (black/copper · greens · blues · reds), never a rainbow. This is the strongest
  common thread.
- **One clear focal subject** with generous negative space around it.
- **Soft, flat backgrounds** — a gradient, a single gentle light source, organic
  shapes, or a solid field. No clutter.
- **Low-to-balanced contrast**, restrained and premium in mood.
- **Clean type hierarchy** — one confident headline + a short supporting line;
  logo kept small; text given a calm, high-contrast area to sit in.

## Adding more references

Drop image files here (`.jpg` / `.png` / `.webp`, not gitignored) and commit
them. Run the analyzer on any image with:

```bash
python3 -c "import reference_style as rs; import json; print(json.dumps(rs.analyze_references(['reference/<file>']), indent=2, default=str))"
```
