# 09 · Build Plan — Phases, Tasks, Acceptance, and Agent Prompts

Estimates assume 2–4 people each working with an AI coding agent. They are planning guesses, not guarantees: scale them to your hackathon window. Build in order; each phase ends with something demoable.

## 0. Team split (suggested)

| Track | Owner | Scope |
|---|---|---|
| A · Backend & rules | Naveen (or backend lead) | Phases 1, 2, 6 (API, pipeline, rule engine, orchestrator) |
| B · Console UI | Ananda | Phases 3, 4 (queue, patient detail, intake/review) |
| C · Simulator & content | Kripa | Phase 5 (chat UI, i18n), Telugu/Hindi template review, foods |
| D · Product, QA, demo | Vinay | PRD guardian, clinical review liaison, test plan, demo script, deck |

Adapt freely. **Contract first:** Track B and C can start on day 1 with MSW mocks generated from `04-API-CONTRACT.md` while Track A builds the real API.

## 1. MVP cut line

- **Must:** P0 → P1 → P2 → P3 → P5 (minimal) → hero scenario works with `LLM_PROVIDER=mock`.
- **Should:** P4 (intake with real plan compiler), P6 (orchestrator, demo clock, nutrition), charts.
- **Could:** P7 (voice, WhatsApp, FHIR, deploy).
- **Always:** P8 (demo hardening) in the last 20% of time. Do not skip it.

## 2. Phases

### P0 · Scaffolding (≈ 1–2 h)
**Tasks**
- [ ] Monorepo layout from `CLAUDE.md §5`; `git init`; `.gitignore`; copy `.env.example`.
- [ ] Backend: FastAPI app factory, `/health`, config, DB session, create tables from `schema.sql`, seed loader skeleton, ruff + pytest configured.
- [ ] Frontend: `create-next-app` (TypeScript, Tailwind, App Router), `shadcn init`, add `tokens.css`, fonts (Inter, Noto Sans Telugu, Noto Sans Devanagari, optional Fraunces), layout with `SyntheticRibbon`.
- [ ] OpenAPI export script + `openapi-typescript` npm script.
- [ ] Run rule reference tests: `python3 seed/rules/reference_engine.py` (36/36).

**Done when:** `GET /health` returns ok; frontend shows a styled empty console; one command starts each side.

**Agent prompt**
> Read `CLAUDE.md` and `docs/02-ARCHITECTURE.md`. Implement Phase P0 from `docs/09-BUILD-PLAN.md`. Create the repo skeleton exactly as in CLAUDE.md §5. Do not implement features beyond scaffolding. Show me the run commands and what you assumed.

### P1 · Domain core + rule engine (≈ 3–4 h)
**Tasks**
- [ ] SQLAlchemy models for all tables in `05-DATA-MODEL.md`.
- [ ] `core/clock.py` (demo clock), `core/audit.py`.
- [ ] Rule loader + engine ported from `seed/rules/reference_engine.py` into `app/rules/` with Pydantic models; load pack at startup; **fail startup on invalid pack**.
- [ ] `fact_builder` (medication streaks, symptom windows, vitals, no-response).
- [ ] `sentinel`: evaluate, family reduction, dedupe, **merge** (see 03 §5.4), SLA due times, alert + alert_events + audit.
- [ ] Endpoints: auth, patients CRUD, alerts list/detail/actions, rules read, `/rules/evaluate`, `/demo/seed|reset`.
- [ ] Seed loader populates 5 patients, plan for P001, history from `scenario_ramesh.json`.

**Tests:** golden rule cases; fact builder streak cases; sentinel dedupe/merge/upgrade; API contract tests.
**Done when:** `POST /rules/evaluate` with hero facts returns `R-ADH-01` + `R-COMBO-01`; `/demo/seed` makes `GET /alerts` return the seeded alerts for P002, P003, P005.

**Agent prompt**
> Read CLAUDE.md, docs/03, 04, 05 and `seed/rules/*`. Implement Phase P1. Port `reference_engine.py` faithfully; the golden tests in `diabetes_htn_v1.tests.json` must pass unchanged. Implement sentinel merge behaviour as written in docs/03 §5.4. Add pytest tests. Do not call any LLM in this phase.

### P2 · Conversation pipeline (≈ 4–5 h)
**Tasks**
- [ ] Provider interfaces + `MockLLMProvider` (keyword tables from docs/07 §3.4, plan canned output, template summaries).
- [ ] `intent_extractor` with post-processing and **critical keyword safety net**.
- [ ] `reply_composer` (templates, rendering, validator with ≥ 20 unsafe-string tests).
- [ ] `pipeline.handle_inbound_message` end to end (docs/03 §4).
- [ ] Endpoints: `/sim/session`, `/sim/messages`, `GET /patients/{id}/messages`, timeline, adherence, vitals.
- [ ] SSE `/alerts/stream` broadcaster.
- [ ] Eval harness over `seed/eval_utterances.json` (critical recall 100%).

**Done when:** posting the hero sentence in Telugu to `/sim/messages` returns `escalate_notified` in Telugu and creates one HIGH alert (`R-COMBO-01`) with 2 evidence messages, visible on the SSE stream.

**Agent prompt**
> Implement Phase P2 following docs/03 §4, docs/07 and docs/04 §6. Everything must work with LLM_PROVIDER=mock and no network. Safety rules SR-1 to SR-9 apply. Add the eval harness and make critical-symptom recall 100% on `seed/eval_utterances.json`. Report any eval cases you could not satisfy.

### P3 · Console UI: queue, alert drawer, patient detail (≈ 5–6 h)
**Tasks**
- [ ] Generate API types; `lib/api.ts`; TanStack Query; `useAlertStream`.
- [ ] Components: SeverityBadge, AlertCard, DueChip, KpiTile, EvidenceQuote, RuleChip, ConfidenceBadge.
- [ ] `/queue` with KPI strip, filters, live updates, toast, keyboard nav.
- [ ] Alert drawer with actions (approve call, acknowledge, snooze, resolve w/ required note).
- [ ] `/patients`, `/patients/[id]` tabs (Overview, Conversation, Care plan, Alerts, Audit).
- [ ] Login with demo accounts.

**Done when:** acceptance checklist items 1–3 and 5–6 in `06 §11` pass against the real backend.

**Agent prompt**
> Read CLAUDE.md, docs/04, docs/06 and `frontend/styles/tokens.css`. Implement Phase P3 exactly to the wireframes and component specs in docs/06 §3–4. Use generated OpenAPI types. Severity must be shown with icon + label + colour. Build against MSW mocks first if the backend isn't ready, then switch to the real API.

### P4 · Intake and plan review (≈ 4 h)
**Tasks**
- [ ] Backend: documents, `care-plans/draft` (PlanCompiler with span verification), edit/approve/activate with versioning and audit.
- [ ] Gemini provider (structured output, timeout, repair retry) behind the interface.
- [ ] Frontend `/patients/[id]/intake`: paste → draft → two-pane review → approve → activate; "Load sample" button.

**Done when:** pasting `seed/discharge_summary_ramesh.txt` yields the plan in `…expected_plan.json` (mock) or an equivalent plan (Gemini); activation is blocked until approval; a fabricated medicine is dropped with a warning.

**Agent prompt**
> Implement Phase P4 per docs/03 §9, docs/07 §4, docs/04 §5 and docs/06 §4.4. Doses must be copied verbatim and every item must carry a verified source span. Add a test that a hallucinated medicine is dropped. Gemini model name must come from env.

### P5 · Patient simulator (≈ 4–5 h)
**Tasks**
- [ ] `/sim` picker and `/sim/[patientId]` phone frame, bubbles with `lang`, quick replies, language toggle, Show English, typing indicator.
- [ ] Side panel "What Setu understood" (extracted data, rule outcome).
- [ ] Persisted conversation (`GET /patients/{id}/messages`), polling/SSE for scheduled check-ins.
- [ ] UI strings in `lib/i18n.ts` (en/te/hi).

**Done when:** you can run the full hero scenario by tapping and typing in Telugu while the console updates live.

**Agent prompt**
> Implement Phase P5 per docs/06 §4.7 and §6. Telugu and Hindi must render with correct fonts and line-height. The simulator header must say "Setu (demo)" and the first message must be the disclaimer template. Never imply this is real WhatsApp.

### P6 · Orchestrator, demo clock, nutrition, charts (≈ 4–5 h)
**Tasks**
- [ ] Orchestrator tick (check-ins at 08:00/19:00 IST on demo clock), missed check-in marking, no-response rule inputs.
- [ ] `/demo/*` endpoints and `/demo` page (time travel, scenario step, provider switch).
- [ ] Nutrition engine (daily tip + meal feedback) using `foods_andhra.json`; tests that `avoid/limit` foods never get recommended for the patient's conditions.
- [ ] Adherence strip + vitals chart with threshold bands.

**Done when:** pressing +1 day produces check-ins and history; Padma (P005) shows the no-response MEDIUM alert; the morning check-in ends with a food tip in the patient's language.

**Agent prompt**
> Implement Phase P6 per docs/03 §7–8 and docs/04 §10. All time must go through `core.clock`. Nutrition output must be template-only with localised food names; no quantities or calories.

### P7 · Stretch (as time allows, in this order)
1. Rules page (FR-19). 2. Sarvam speech (FR-16): STT for voice notes, TTS for replies. 3. Audit tab polish. 4. FHIR export (FR-23). 5. WhatsApp Cloud API adapter (FR-17): webhook verification, signature check, 24-hour window handling, test number. 6. Deploy (Vercel + Render/Cloud Run + Postgres).

### P8 · Demo hardening (≈ 2–3 h, **mandatory**)
- [ ] Run the demo script (`10-DEMO-AND-TESTS.md`) 3 times in a row on the demo machine.
- [ ] Full reset → seed → hero flow in under 2 minutes.
- [ ] Test offline (airplane mode) with mock provider.
- [ ] Record a 2-minute backup video; export screenshots for the deck.
- [ ] Fix top 5 UI papercuts; check 1280×720 projector layout.
- [ ] Final safety checklist (`08 §7`) and clinical review log updated.
- [ ] Tag `v0.1-demo`; make a clean-clone setup test from README.

## 3. Parallel-agent workflow tips

- Give each agent **one phase and the exact docs to read**. Don't paste the whole pack into one prompt.
- Ask each agent to end with: *what changed, how to run it, what is stubbed, assumptions*.
- After each phase: run tests, commit, and update `docs/ASSUMPTIONS.md`.
- Use a second agent as **reviewer** with this prompt: "Review the diff against CLAUDE.md §3 safety rules and docs/04 contract. List violations only; do not fix."
- Keep one human owner for `docs/04-API-CONTRACT.md`. API drift is the main cause of integration pain.

## 4. Risk watch-list during the build

| Risk | Early signal | Response |
|---|---|---|
| Contract drift | Frontend fixtures stop matching backend | Regenerate types; fix contract doc first |
| LLM flakiness | Invalid JSON, slow replies | Raise mock coverage; keep real LLM optional |
| Telugu rendering issues | Boxes or clipped text | Verify fonts load; add `lang` attributes; test early in P0 |
| Scope creep | New features before P3 done | Check MVP cut line |
| Demo-day network | Wi-Fi unreliable | Run local, mock provider, backup video |

## 5. Pre-submission checklist

- [ ] Hero demo works 3× in a row
- [ ] README lets a stranger run it in < 10 minutes
- [ ] Synthetic-data ribbon visible; no real data anywhere
- [ ] Rule pack shows DRAFT honestly (or APPROVED with a named clinician)
- [ ] Deck numbers match what the product does
- [ ] Source links on the last slide open
- [ ] Backup video and screenshots saved
