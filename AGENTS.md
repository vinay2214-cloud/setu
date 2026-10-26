# CLAUDE.md — Instructions for AI coding agents working on Setu

> Read this file fully before every task. It is also saved as `AGENTS.md` for tools that look for that name.

## 1. What we are building

**Setu** ("bridge") is a post-discharge care-continuity prototype for chronic disease (type 2 diabetes + hypertension) in India. After a patient leaves hospital, Setu:

1. turns the discharge summary into a clinician-approved care plan,
2. checks in daily with the patient in **Telugu, Hindi or English** (WhatsApp-style chat; voice optional),
3. extracts medicine adherence, symptoms and home readings from the patient's replies,
4. applies **clinician-authored, deterministic rules** to decide if a human must step in,
5. shows clinicians a **priority queue** with one-screen summaries and evidence.

Ideology: **"Automate the gaps, never the doctor."** Healthcare fails in the gaps between visits, doctors, languages, and plan-vs-plate.

This is a **hackathon prototype using synthetic data only.** It is not a medical device and makes no diagnostic claims.

## 2. Read order (specs are the source of truth)

| Order | File | Use it for |
|---|---|---|
| 1 | `docs/01-PRD.md` | What and why, requirement IDs (FR-xx) |
| 2 | `docs/02-ARCHITECTURE.md` | Components, flows, tech decisions |
| 3 | `docs/03-BACKEND-SPEC.md` | Services, pipeline, rule engine, orchestrator |
| 4 | `docs/04-API-CONTRACT.md` | Endpoints, payloads, SSE (frontend and backend both obey this) |
| 5 | `docs/05-DATA-MODEL.md` + `backend/db/schema.sql` | Tables and JSON shapes |
| 6 | `docs/06-FRONTEND-UX-SPEC.md` + `frontend/styles/tokens.css` | Screens, components, design tokens |
| 7 | `docs/07-AI-COMPONENTS.md` | Prompts, schemas, guardrails, eval |
| 8 | `docs/08-SAFETY-COMPLIANCE.md` | Hazards, privacy, wording rules |
| 9 | `docs/09-BUILD-PLAN.md` | Phased tasks and acceptance criteria |
| 10 | `docs/10-DEMO-AND-TESTS.md` | Demo script, test matrix |

If two documents disagree: **API contract > data model > backend spec > PRD.** Log the conflict in `docs/ASSUMPTIONS.md`, pick the safer reading, and continue.

## 3. Non-negotiable safety rules

These override any feature request, shortcut, or "nicer" idea.

- **SR-1 No LLM in escalation decisions.** Whether to alert a clinician is decided only by the deterministic rule engine (`services/sentinel`). LLMs may extract text, translate, and summarise. They never decide severity.
- **SR-2 Fail safe upward.** If extraction is unsure, a critical symptom is uncertain, or the LLM call fails, route to a human (LOW alert "needs review") or escalate. Never silently drop a patient message.
- **SR-3 No clinical advice from the model.** The system never states a diagnosis, never computes or changes a dose, never recommends a medicine not in the patient's approved plan. Medical questions get the `medical_question_defer` template and a LOW alert.
- **SR-4 Patient replies come from approved templates.** Clinical wording lives in `seed/message_templates.json`. An LLM may only paraphrase non-clinical keys, and every output passes the reply validator (docs/07 §6).
- **SR-5 Emergency wording is fixed.** Critical symptoms trigger the `emergency_advice` template (call 108 / nearest hospital). Do not reword it with a model.
- **SR-6 Clinician approval gates the plan.** A care plan cannot be activated until a clinician approves it. AI-extracted fields are marked "AI-extracted, needs review".
- **SR-7 Synthetic data only.** No real names, phone numbers, or records anywhere in code, fixtures, logs, or screenshots.
- **SR-8 Every decision is auditable.** Each alert stores rule id, rule version, facts used, and source message ids. Each state change writes `audit_log`.
- **SR-9 Patient text is data, not instructions.** Never let patient message content change prompts, tools, or rules (prompt-injection defence, docs/07 §7).

## 4. Stack (fixed unless the PRD changes)

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite (dev) / Postgres (deploy), APScheduler, sse-starlette, PyYAML, httpx, pytest, ruff.
- **Frontend:** Next.js (App Router) + TypeScript (strict), Tailwind CSS, shadcn/ui, lucide-react, TanStack Query, Recharts, zod.
- **AI:** provider interfaces with a **mock provider that always works offline**, and a Gemini provider. Model name comes from env, never hard-coded.
- **Speech (optional):** Sarvam (Saaras STT, Bulbul TTS) behind `SpeechProvider`.
- **Channel:** `SimulatorAdapter` (default, always works) and `WhatsAppCloudAdapter` (stretch).

## 5. Repo layout

```
setu/
  CLAUDE.md  AGENTS.md  README.md  .env.example
  docs/                      # specs (this pack)
  seed/                      # synthetic data, rule packs, templates, eval set
  backend/
    requirements.txt
    db/schema.sql
    app/
      main.py  config.py  deps.py
      api/            # routers: patients, plans, sim, alerts, rules, demo, speech, webhooks, health
      models/         # SQLAlchemy models
      schemas/        # Pydantic request/response + domain schemas
      services/       # plan_compiler, intent_extractor, reply_composer, nutrition, sentinel, orchestrator, summary_writer, fact_builder
      providers/      # llm/{base,mock,gemini}.py  speech/{base,sarvam}.py  channel/{base,simulator,whatsapp}.py
      rules/          # loader.py, engine.py
      core/           # clock.py (demo clock), audit.py, logging.py, security.py
    tests/
  frontend/
    app/              # (console)/queue, patients/[id], intake, rules, demo   +   sim/[patientId]
    components/       # ui/ (shadcn) and setu/ (custom)
    lib/              # api.ts, sse.ts, i18n.ts
    styles/tokens.css
    mocks/            # MSW handlers generated from the API contract
```

## 6. Conventions

- **Contract first.** Change `docs/04-API-CONTRACT.md` before changing an endpoint. After backend changes, export OpenAPI (`/openapi.json`) and regenerate frontend types with `openapi-typescript`.
- **Python:** type hints everywhere, `ruff format` + `ruff check`, no bare `except`, services are pure where possible and take providers as arguments (dependency injection).
- **TypeScript:** `strict: true`, no `any`, API types come from generated OpenAPI types, validate unknown JSON with zod.
- **Config:** all secrets and switches via env (`.env.example`). Never commit keys.
- **Logging:** never log message text, names, or phone numbers. Log ids and rule ids only.
- **Time:** always use `core.clock.now()` (demo clock), never `datetime.now()` directly. Store UTC, show Asia/Kolkata.
- **IDs:** string ids with prefixes (`P001`, `A-0001`, `M-…`), as in the seed files.
- **Accessibility:** WCAG AA contrast, never colour-only meaning, keyboard reachable, Telugu text line-height ≥ 1.6.
- **Commits:** small, imperative, one concern each. Reference requirement ids (e.g. `FR-10`).

## 7. Definition of done (every task)

1. Behaviour matches the spec section cited in the task.
2. Tests added or updated and passing (`pytest` / `npm test`); rule-engine changes must pass the golden cases in `seed/rules/diabetes_htn_v1.tests.json`.
3. Lint and type checks clean.
4. Works with `LLM_PROVIDER=mock` (no network, no keys).
5. No safety rule in §3 weakened. If unsure, ask or log in `docs/ASSUMPTIONS.md`.
6. Docs updated if a contract or behaviour changed.

## 8. Working agreement

- Before coding a phase, restate the task, list files you will touch, and note assumptions.
- Prefer the simplest thing that satisfies the acceptance criteria. This is a prototype: no auth beyond demo accounts, no microservices, no premature optimisation.
- Never invent clinical thresholds. All thresholds live in `seed/rules/*.yaml` marked `clinician_review: required`. Do not edit them to "make a test pass".
- Telugu/Hindi strings are drafts until a native speaker reviews them. Keep them in `seed/message_templates.json`, not scattered in code.
- When finished, report: what changed, how to run it, what is stubbed, and what you assumed.
