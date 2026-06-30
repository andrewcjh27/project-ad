# Project AD — Product & Technical Plan

*AI-generated, brand-personalized advertising at top-agency quality.*

Status: Planning draft · Owner: Junho · Last updated: 2026-06-30

> **Current scope: static image + poster ads only.** Video is architected for (the spec is output-type-generic) but **deferred** — it's materially harder and is not in the current build. See §7 Phasing.

---

## 1. Vision & positioning

Project AD is a software product that designs and produces personalized advertisements for a customer based on their data, fit to their interests and the advertising brand's identity. The quality bar is **top agency / brand campaign**: the output must read as though a professional creative agency produced it, not an AI tool.

**Output focus (now): static image and poster ads.** Video remains a future phase — the architecture (layered ad-spec) supports it, but the current product targets image/poster only to keep quality and build complexity manageable.

Generated ads are **editable** by a designer for final retouch — exported to Figma as native layers, not flattened images (see `Figma-Handoff.md`).

**Go-to-market path: internal/agency tool now, SaaS-ready architecture underneath.**
We build the generation pipeline, brand-identity layer, and quality system as clean, API-driven services. We use them internally with a human reviewer in the loop first — capturing revenue and learning what "good" means against real client work. When the automated quality system is trusted enough to shrink the human gate, we wrap a self-serve UI on the same backend and flip to SaaS. This avoids a rebuild and front-loads quality over scale-plumbing.

**Why not pure SaaS first:** self-serve forces multi-tenancy, billing, abuse handling, and quality-without-a-human-gate — months of work unrelated to ad quality, with non-designers feeding messy inputs and no one catching bad output. We earn the right to scale by first proving quality.

---

## 2. The core principle: agency quality requires layered compositing

A single text-to-image generation will not reliably reach agency standard. Image models excel at imagery but fail at exactly what agencies are judged on: precise typography, exact brand color, logo integrity, legible legal text, and deliberate layout. The product therefore treats generation as **one layer in a composited pipeline**, not the whole ad.

Two generation modes, chosen per-ad by the system:

- **Full-AI mode** — for imagery-dominant ads with little/no text (lifestyle, mood, a tolerable 2–3 word tagline). Faster and cheaper; acceptable when there's no typographic or brand-precision risk.
- **Layered-compositing mode** *(default for client-facing work)* — AI generates **imagery only**; text, layout, logos, and legal copy are rendered deterministically. This is the only mode that survives agency scrutiny on type and color.

The art-director LLM decides which mode each ad uses.

---

## 3. The generation pipeline (layered compositing)

Every ad is assembled from separable layers, each produced by the best-suited tool:

| Layer | Produced by | Notes |
|---|---|---|
| **Imagery** | Generative model (API) | Backgrounds, product scenes, visual elements only. Never text or logos. Constrained by brand-derived style. |
| **Composition** | Deterministic renderer + brand templates | Layout, grids, safe zones, hierarchy. The AI proposes; the template system disposes. |
| **Typography** | Deterministic renderer (real fonts) | Headlines and body always crisp, on-brand, legible. AI writes the copy; it never renders it. |
| **Brand assets** | Deterministic placement from asset library | Logos, legal lines, fixed marks placed pixel-exactly. Never regenerated. |
| **Art direction** | Orchestrator LLM | Reads customer data + brand identity (RAG), decides concept, writes copy, picks template, writes image prompt → emits a **structured ad spec**. |

**Flow:**
`customer data + brand RAG → art-director LLM produces a structured ad spec → imagery generated → composited with real type, layout & brand assets → automated QC → human review`

The output is a machine-readable **spec** plus a rendered file — so every ad is editable, reproducible, versioned, and not a black-box image. The spec is the contract that lets us swap models, add output types, and enforce brand rules without rewrites. **It is the single most important artifact in the system** (specified separately in `Ad-Spec-Schema.md`).

The same spec drives all three output types: posters are composition-heavy specs; video is the same spec feeding a motion renderer instead of a static one. We design the spec format once.

---

## 4. Brand-identity layer (the moat) — per-brand, isolated

Every brand has a distinct identity, so each brand is its own **isolated identity package** — its own config and its own document corpus. Nothing is averaged or shared across brands; identity is retrieved per-brand at generation time (multi-tenant by design).

Brand knowledge splits into two kinds, consumed differently:

- **Hard constraints** — exact hex colors, approved fonts, logo clear-space, min sizes, banned words, mandatory legal lines. Stored as **structured config** (per-brand JSON/YAML) and **enforced deterministically by the renderer**. Never paraphrased or fuzzily retrieved — you don't want a model *recalling* a hex code; you want it loaded as fact.
- **Soft guidance** — tone, mood, brand reasoning, example campaigns, do's and don'ts. This is genuine **RAG**: chunked, embedded, and retrieved to inform the art-director's concept and copy.

The art-director LLM receives both — config injected as constraints, docs retrieved as guidance — and the renderer enforces the config regardless of what the LLM says. That separation is what makes output *reliably* on-brand instead of *occasionally* on-brand.

Because guidelines are currently informal, we author them directly in the structure the system needs (see `Brand-Identity-Template.md`). The template doubles as the new-brand onboarding asset, making each additional brand fast to add without engineering.

---

## 5. Quality system (how we hit and hold the agency bar)

Generation gets ~80%; this stage gets the last 20% that separates "looks AI-made" from "looks agency-made." Four layers, cheapest first:

1. **Automated QC gates** *(deterministic, runs on every ad before a human sees it).* Brand color within tolerance, logo present & uncorrupted, text legible & unclipped, contrast/accessibility thresholds, safe-zone compliance, required legal lines present, correct resolution & aspect ratio. Failures auto-reject and regenerate.
2. **AI critique pass** *(vision model as "creative director").* Scores the ad against the brand's soft guidance (on-brand? compelling? clear hierarchy?) and approves, requests regenerate, or flags for human. Catches taste failures the deterministic checks can't.
3. **Human-in-the-loop review** *(v1 quality guarantee).* A human approves every client-facing ad. The product's job is to make review fast: show the ad, its spec, the rules it was checked against, and one-click approve / regenerate / edit.
4. **Feedback loop.** Every human decision is logged against the spec. This tunes the AI critique pass to match human reviewers over time, gradually relaxing the human gate — which is what eventually unlocks the SaaS flip.

Order matters: never spend a reviewer's attention on something a color-check should have caught.

---

## 6. Tech stack & build vs. buy

**Principle: buy the models, build the spec / orchestration / QC.** Models are commoditizing; durable value is the spec format, brand-identity layer, and quality system. Stay model-agnostic.

| Component | Approach | Choice |
|---|---|---|
| Imagery generation | Buy (API, behind adapter) | Imagen / Flux / GPT-image-class; swappable & A/B-able. No self-hosting early. |
| Art-director + critique LLM | Buy (API, behind adapter) | Frontier model (Claude / GPT-class) for orchestration & vision critique. |
| Renderer / compositing | **Build** | HTML/CSS-to-image (Puppeteer/Playwright) or SVG for static & posters — pixel-perfect type/layout, easy to hire for. |
| Video renderer | **Build (deferred)** | Remotion (React) — same spec→render model. Out of current scope; image/poster only for now. |
| Segmentation | **Build** | Cluster users into cohorts; generate per segment, not per user (see `Audience-Segmentation-and-Scaling.md`). |
| Product matching | **Build** | Hybrid retrieve→rank over embeddings (see `Product-Matching-and-Recommendation.md`). |
| Designer handoff | **Build** | Figma plugin: spec → editable layers for final retouch (see `Figma-Handoff.md`). |
| RAG store | Buy (boring) | Vector DB with hard per-brand tenant isolation (pgvector or dedicated). |
| Backend | **Build** | Job-queue architecture (async, multi-step, retry-heavy). The spec is the object flowing through: segment → match → art-direct → generate → composite → QC → review. |
| Data | Postgres | Specs, brand configs, segments, audit/decision log. |
| Frontend (v1) | **Build** | Internal review/editing console (with "Open in Figma" retouch path) — the only UI needed until the SaaS flip. |

---

## 7. Phasing

*Current focus: image + poster (Phases 0–2). Video (Phase 3) is deferred.*

- **Phase 0 — spec + one brand, one output (static image).** Define the ad-spec schema, build the static renderer, stand up one brand's identity package, wire the art-director LLM and deterministic QC gates. *Goal: one genuinely on-brand static ad end-to-end, human-reviewed.* De-risks the whole bet.
- **Phase 1 — quality + throughput + scale.** Add AI critique pass, review console, feedback log, the brand-onboarding template, **segmentation** (generate per cohort), **product matching**, and the **Figma retouch handoff**. Run real client work internally.
- **Phase 2 — posters / layout-heavy.** Second output type; proves the spec generalizes. Mostly renderer/template work; pipeline unchanged. **This completes the current scope (image + poster).**
- **Phase 3 — video (deferred / out of current scope).** Remotion renderer on the same spec. Highest effort; revisit after image/poster is solid.
- **Phase 4 — SaaS flip.** Self-serve UI, multi-tenant hardening, billing, abuse controls — only once auto-QC + critique are trusted enough to shrink the human gate.

---

## 8. Team & roles

Critical early ownership:

- **Renderer / compositing owner** — frontend-rendering depth; owns fidelity to templates across static → poster → video.
- **AI orchestration + RAG owner** — art-director prompt design, critique pass, per-brand retrieval and isolation.
- **Embedded designer / art director — from day one.** Defines templates, brand configs, and what "good" means for the critique pass and human review. Without a design voice in the loop, engineers ship something that passes every automated check and still looks AI-made.

---

## 9. Top risks

- **Ad-spec schema design** — everything hinges on it; worth a dedicated design spike before building (see `Ad-Spec-Schema.md`).
- **Renderer fidelity** to brand templates — the difference between on-brand and almost-on-brand.
- **How fast the human gate can safely shrink** — gates SaaS economics; depends entirely on the feedback loop and critique-pass accuracy.
- **Model dependency / cost drift** — mitigated by the adapter layer and model-agnostic spec.
- **Brand-data isolation** — a leak across tenants is fatal to trust; enforce isolation at the storage layer, not just app logic.

---

## 10. Immediate next steps

1. Author the first brand's identity package using `Brand-Identity-Template.md`.
2. Run a design spike on the ad-spec schema (`Ad-Spec-Schema.md`) and validate it against 3–4 real target ads.
3. Build the Phase 0 static renderer against the validated spec.
4. Stand up the deterministic QC gates in parallel.
