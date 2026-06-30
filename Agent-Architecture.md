# Multi-Agent Architecture

*Project AD's generation pipeline is built as a team of **specialized AI agents**, each owning one role, handing off through the shared ad-spec. Specialization beats one monolithic prompt: each agent is small, separately promptable, separately swappable, and separately evaluable — and the division mirrors how a real creative team actually works.*

Status: Draft · Pairs with `Ad-Spec-Schema.md` (v0.2), `Personalization-Design-System.md`, `Product-Matching-and-Recommendation.md`

---

## 1. Why multi-agent (not one big prompt)

- **Specialization → quality.** A copywriter prompt tuned only for brand voice beats a do-everything prompt. Each agent has one job and a focused context.
- **Swappable & evaluable.** Each role can use a different model, be A/B-tested, and be measured on its own metric (copy quality, brand adherence, layout balance) without touching the others.
- **Guardrails per role.** The brand-guardian can hard-veto regardless of what upstream agents produced.
- **Mirrors a creative team.** Strategist → art director → copywriter → designer → creative-director review is a proven division of labor; we encode it.
- **The ad-spec is the shared language.** Agents don't pass prose to each other — they read and write fields of the spec (the contract from `Ad-Spec-Schema.md`). This keeps handoffs structured and auditable.

---

## 2. The agent roster

| # | Agent | Role | Reads | Writes (spec) | Backed by |
|---|---|---|---|---|---|
| 1 | **Strategist** | Turns a segment into a creative brief & angle | segment representative, rulebook | `concept.rationale`, `concept.copy_angle`, `messaging_pillar` | LLM |
| 2 | **Product Matcher** | Picks the product from ranked candidates, with reason | candidate set, segment | `personalization.selected_product`, `selection_reason` | Retrieval+rank + LLM final pick |
| 3 | **Art Director** | Owns the concept, template, imagery prompt, layout & color choices | brief, product, brand config+RAG | `concept.big_idea`, `canvas`, `elements[]` boxes, template, image `prompt` | LLM |
| 4 | **Copywriter** | Writes headline/subhead/CTA in brand voice (respects manual/locked copy) | brief, product, brand voice (RAG) | `elements[type:text].content` (generated ones only) | LLM |
| 5 | **Image Generator** | Produces the imagery layer from the art-director's prompt + brand style | `canvas.imagery[].prompt`, brand imagery rules | the rendered image asset | Image model (API) |
| 6 | **Compositor / Renderer** | Assembles spec into the final pixels (deterministic) | full spec + assets | the rendered ad file | Code (not an LLM) |
| 7 | **Brand Guardian** | Enforces hard brand rules; can veto | spec + render + brand config | `qc.gates.*`, veto/regenerate | Deterministic checks (+ optional LLM) |
| 8 | **Creative-Director Critic** | Scores taste/on-brand-ness; approve / regen / flag | render + brand soft guidance | `qc.ai_critique` | Vision LLM |
| — | **Orchestrator** | Routes work, manages retries, escalates to human | all of the above | pipeline state | Code + policy |

> Agents 1–4, 8 are LLM-backed (specialized prompts). 5 is an image model. 6 is deterministic code. 7 is mostly deterministic with an optional LLM assist. The Orchestrator is control logic, not a model.

---

## 3. Orchestration flow

```
            ┌──────────────┐
 segment ──▶│ 1 Strategist │── brief/angle ─┐
            └──────────────┘                ▼
            ┌────────────────┐      ┌─────────────────┐
candidates ▶│ 2 ProductMatch │────▶ │ 3 Art Director  │── concept, layout, image-prompt
            └────────────────┘      └─────────────────┘
                                            │  ├──────────────┐
                                            ▼  ▼              ▼
                                   ┌────────────┐   ┌──────────────────┐
                                   │4 Copywriter│   │5 Image Generator │
                                   └────────────┘   └──────────────────┘
                                            │              │
                                            └──────┬───────┘
                                                   ▼
                                          ┌───────────────────┐
                                          │ 6 Compositor      │── rendered ad
                                          └───────────────────┘
                                                   ▼
                              ┌────────────────────────────────────┐
                              │ 7 Brand Guardian  → 8 CD Critic     │
                              └────────────────────────────────────┘
                                   pass ▼            fail ▼
                              human review        regenerate (targeted)
```

**Targeted regeneration:** when the Guardian or Critic rejects, the Orchestrator sends the work back to the *specific* responsible agent — bad color → Image Generator; off-voice headline → Copywriter; weak layout → Art Director — not a blind full restart. This is the big efficiency win of role separation.

---

## 4. Handoff contract

Agents communicate **only through the ad-spec**, never free-form. Each agent:
1. receives the current spec (+ its own focused context: brand RAG slice, candidate set, etc.),
2. writes only its owned fields,
3. leaves a short rationale in the spec for audit (`provenance` / `selection_reason` / `ai_critique.notes`).

This makes the whole generation **traceable** — for any finished ad you can see which agent decided what and why, which feeds the human reviewer and the feedback loop.

---

## 5. Guardrails & authority

- **Brand Guardian has veto power** over every other agent — a hard brand-rule violation (color out of tolerance, banned word, logo misuse, contrast fail) blocks the ad regardless of how good the concept is. Deterministic, non-negotiable.
- **Manual copy is protected:** the Copywriter must not touch `copy.source == "manual"` elements (enforced by the spec, re-checked by the Guardian).
- **Critic ≠ Guardian:** the Critic judges *taste* (subjective, scored), the Guardian judges *rules* (objective, pass/fail). Both must pass.
- **Human is final authority** in v1 — the Orchestrator escalates anything the Critic flags or that fails after N regenerations.

---

## 6. Why this maps onto the build cleanly

- Each agent = one service with a pinned prompt + model behind an adapter (same model-agnostic principle as the rest of the stack).
- The Orchestrator is the existing job-queue: the spec is the job, each agent a stage, retries are targeted regenerations.
- New capability = new/upgraded agent, not a rewrite (e.g. a future "Motion" agent for video reuses the same brief + spec).

---

## 7. Demonstrated in code

`generation_pipeline.py` implements this roster end-to-end for the Starbucks fall/PSL segment from the spike — Strategist → Matcher → Art Director → Copywriter → Image (stub) → Compositor → Guardian → Critic — producing a real rendered ad plus the spec each agent contributed to. LLM/image-model agents use rule-based stand-ins where no API is wired (clearly marked), exactly as the spike used TF-IDF for embeddings; the *interfaces and handoffs* are production-shaped.
