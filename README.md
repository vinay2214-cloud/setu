# Setu — AI care bridge for post-discharge chronic care

> **Automate the gaps, never the doctor.**
> Team **Avengers** · Unstop hackathon, MBU · Healthcare & Technology
> Prototype · Synthetic data only · Not for clinical use

Setu turns a discharge summary into a clinician-approved care plan, checks in with the patient daily in **Telugu, Hindi or English**, listens for missed medicines, symptoms and readings, and alerts a clinician through **transparent, clinician-written rules** when a human is needed.

## What is in this pack

```
CLAUDE.md / AGENTS.md        Instructions every AI coding agent must read first
docs/
  01-PRD.md                  Product requirements, personas, user stories, FR-xx list
  02-ARCHITECTURE.md         Components, sequence diagram, technology decisions
  03-BACKEND-SPEC.md         Pipeline, rule engine, orchestrator, services
  04-API-CONTRACT.md         Every endpoint, payload and SSE event (source of truth)
  05-DATA-MODEL.md           Tables, vocabularies, JSON shapes
  06-FRONTEND-UX-SPEC.md     Screens, wireframes, components, accessibility
  07-AI-COMPONENTS.md        Prompts, schemas, guardrails, evaluation
  08-SAFETY-COMPLIANCE.md    Hazard analysis, privacy, clinical review checklists
  09-BUILD-PLAN.md           Phases, tasks, acceptance criteria, ready-made agent prompts
  10-DEMO-AND-TESTS.md       Demo script, jury Q&A, test matrix
  11-REFERENCES.md           Verified sources and how to find GitHub/Figma references
  ASSUMPTIONS.md             Decision log (keep updating)
backend/db/schema.sql        Database schema
backend/requirements.txt     Python dependencies
frontend/styles/tokens.css   Design tokens
seed/                        Synthetic data, rule pack + golden tests, templates, foods, eval set
.env.example                 Configuration
```

## How to start (60 minutes to a running skeleton)

1. **Read** `CLAUDE.md` then `docs/01-PRD.md` and `docs/09-BUILD-PLAN.md` (15 min, whole team).
2. **Create the repo** and copy this pack in: `git init && git add . && git commit -m "Add Setu spec pack"`.
3. **Check the rule engine reference** (needs Python 3 and PyYAML):
   ```bash
   pip install pyyaml
   python3 seed/rules/reference_engine.py      # expect: 36/36 passed; 22 rules loaded
   ```
4. **Open your AI coding agent in the repo root** and paste the **P0 prompt** from `docs/09-BUILD-PLAN.md`. Continue phase by phase (P1, P2, …) giving each agent only its phase and the docs it names.
5. **Run locally** (after P0):
   ```bash
   # backend
   cd backend && python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp ../.env.example .env
   uvicorn app.main:app --reload --port 8000

   # frontend (new terminal)
   cd frontend && npm install && npm run dev      # http://localhost:3000
   ```
   Default `LLM_PROVIDER=mock` needs no keys and no network.

## Operating rules in one minute

- Specs are the source of truth. If docs conflict: API contract > data model > backend spec > PRD.
- Safety rules SR-1…SR-9 (in `CLAUDE.md`) are never traded for speed.
- Thresholds, Telugu/Hindi strings and food suitability are **drafts** until a clinician, native speaker and dietitian review them.
- Keep the demo reliable: mock AI, demo clock, reset + seed in one click, backup video.

## Hero demo in one line

Ramesh (58, Telugu) skips a tablet two days running and mentions swollen feet → Setu replies in Telugu → a **HIGH** alert appears on the clinician's queue with quoted evidence, rule id, and "Call within 4 hours". Details: `docs/10-DEMO-AND-TESTS.md`.

## Disclaimer

Setu is a care-coordination prototype. It does not diagnose, prescribe, or replace clinicians. In an emergency call 108.
