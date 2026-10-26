# 01 · Product Requirements Document (PRD) — Setu

| | |
|---|---|
| **Product** | Setu — AI care bridge for post-discharge chronic care |
| **Team** | Avengers (Vinay, Ananda, Kripa, Naveen) |
| **Event** | Unstop hackathon, MBU — Healthcare & Technology |
| **Version** | 1.0 (prototype scope) |
| **Status** | Ready to build |
| **Data** | Synthetic only |

---

## 1. Overview

Setu keeps a patient safe between hospital discharge and the next clinic visit. It converts the discharge plan into daily actions (medicines, food, readings, warning signs), talks to the patient in their language on a familiar channel, notices when things drift, and brings a clinician in early with a clear, evidence-backed summary.

**One-line ideology:** *Automate the gaps, never the doctor.*

## 2. Problem

Hospitals treat an episode; chronic disease lasts a lifetime. After discharge, four gaps open:

1. **Between visits** — weeks of silence; early warning signs are missed.
2. **Between doctors** — several prescribers, no one reviews the whole picture.
3. **Between languages** — instructions are written in English; patients live in Telugu/Hindi.
4. **Between plan and plate** — "eat healthy" is not actionable for local diets and budgets.

Evidence base (see deck sources): 101M adults with diabetes and 315M with hypertension in India (ICMR-INDIAB, 2023); average long-term-therapy adherence about 50% in developed countries and lower elsewhere (WHO, 2003); people with diabetes make up 10–25% of unplanned 30-day readmissions in published cohorts. India-specific post-discharge data is scarce, which the pilot is meant to measure.

## 3. Goals and non-goals

### Goals (prototype)
- G1. Show a **closed loop end to end**: plan → check-in → listen → detect → escalate → adapt.
- G2. Prove **local-language, low-friction** patient interaction (Telugu/Hindi/English).
- G3. Prove **clinician trust**: deterministic rules, evidence, approval gates, audit trail.
- G4. Show a credible **nutrition differentiator** using local foods.
- G5. Be **demo-reliable**: works offline with a mock AI provider and a controllable demo clock.

### Non-goals (prototype)
- Diagnosis, dose changes, or treatment recommendations by AI.
- Real patient data, real WhatsApp numbers, production auth, billing.
- EHR integrations beyond a FHIR-shaped export (stretch).
- IVR voice-call fallback (described in the deck; not built).
- Mobile native apps.

## 4. Personas

| Persona | Description | Needs | Pain today |
|---|---|---|---|
| **Ramesh, 58** (patient) | Type 2 diabetes + hypertension, Vijayawada, Telugu speaker, uses WhatsApp, low English literacy | Simple daily steps in Telugu, reminders, a person when something is wrong | Stops tablets when he feels well; instructions in English; no one to ask |
| **Dr. Anitha** (clinician, fictional) | Physician in a busy clinic | A short list of who needs a call today, with reasons | No visibility between visits; follow-up calls are ad hoc |
| **Sunita** (community health worker, stretch) | ASHA/nurse who can phone or visit | A task list with context | Gets vague referrals |
| **Judge** (evaluator) | Assesses impact, uniqueness, feasibility, safety | Clear problem, working demo, honest limits | — |

## 5. Core user journeys

**J1 — Intake and approval (clinician).** Paste discharge summary → AI drafts a care plan with source highlights and confidence → clinician edits and approves → activates monitoring.

**J2 — Daily check-in (patient).** Morning message in Telugu → patient replies by tap or text (voice optional) → Setu records medicines/readings/symptoms → replies with acknowledgement and a food tip.

**J3 — Drift detection (system).** Rules evaluate after every patient message and on schedule → alert created with severity, rule id, evidence.

**J4 — Triage and action (clinician).** Priority queue updates live → open alert → read summary and quoted evidence → approve call / acknowledge / snooze / resolve with note.

**J5 — Emergency path (patient + clinician).** Critical symptom reported → fixed emergency wording to patient (call 108 / go to hospital) → CRITICAL alert to clinician.

## 6. Functional requirements

Priority: **M** = must (demo breaks without it), **S** = should, **C** = could (stretch).

| ID | Requirement | Pri |
|---|---|---|
| FR-01 | Enrol a patient with recorded consent (type, channel, wording version, timestamp). No consent → no messaging. | M |
| FR-02 | Accept a discharge summary as pasted text (PDF upload is stretch). | M |
| FR-03 | AI drafts a structured care plan (diagnoses, medicines, monitoring, diet, red flags, follow-ups) with source spans and per-field confidence. | M |
| FR-04 | Clinician reviews, edits, and approves the plan; activation requires approval. Edits are versioned. | M |
| FR-05 | Schedule morning and evening check-ins per approved plan, driven by the demo-able clock. | M |
| FR-06 | Conversational check-in in Telugu, Hindi, English (text, quick replies). | M |
| FR-07 | Extract intents, medicine events, symptoms (controlled vocabulary), vitals (glucose, BP), meals, questions from patient messages, with confidence. | M |
| FR-08 | Track medicine adherence per medicine per scheduled slot. | M |
| FR-09 | Capture self-reported glucose and BP readings with units and context. | M |
| FR-10 | Evaluate clinician-authored YAML rule packs deterministically; produce severity LOW/MEDIUM/HIGH/CRITICAL. | M |
| FR-11 | Create alerts with dedupe, SLA due time, and live push to the console (SSE). | M |
| FR-12 | Alert detail shows one-screen summary, quoted evidence, rule id/version, suggested action. | M |
| FR-13 | Alert actions: approve call, acknowledge, snooze, resolve with note; all audited. | M |
| FR-14 | Nutrition guidance: daily tip and meal feedback from a local-food database, personalised by conditions and plan restrictions. Qualitative, no calorie claims. | M |
| FR-15 | Patient simulator: phone-frame chat with language toggle, quick replies, optional translation caption. | M |
| FR-16 | Voice notes in (STT) and voice replies out (TTS) for Telugu/Hindi. | S |
| FR-17 | WhatsApp Cloud API adapter (webhook + send). | C |
| FR-18 | No-response escalation (consecutive missed check-ins). | S |
| FR-19 | Read-only rule pack viewer showing thresholds, version, approval status. | S |
| FR-20 | Adherence and vitals charts on patient detail. | S |
| FR-21 | Audit log for plan edits, approvals, alerts, rule evaluations. | M |
| FR-22 | Demo control panel: seed, reset, time-travel (advance days), trigger check-in, toggle mock/real AI. | M |
| FR-23 | FHIR R4 export of a minimal patient bundle. | C |
| FR-24 | Health-worker task list derived from alerts. | C |

## 7. User stories and acceptance criteria (key flows)

**US-01 Plan approval gate** (FR-03, FR-04)
- *Given* a pasted discharge summary, *when* the clinician clicks "Draft plan", *then* a draft plan appears with each medicine showing its source sentence and a confidence badge.
- *Given* a draft plan, *when* the clinician has not approved, *then* "Activate monitoring" is disabled.
- *Given* an edit to a medicine, *then* a new plan version is saved and the audit log records who changed what.

**US-02 Morning check-in** (FR-05, FR-06, FR-08)
- *Given* an active plan and the clock reaching 08:00 IST, *then* the patient receives the greeting, a medicine question with quick-reply buttons, and a glucose and symptom prompt in their language.
- *When* the patient taps "Yes, taken", *then* all morning medicines for that day are recorded as taken.

**US-03 Missed dose and swelling → HIGH alert** (FR-07, FR-10, FR-11, FR-12) — *the hero demo*
- *Given* the patient missed a critical medicine yesterday, *when* they say today's tablet was not taken and report swollen legs, *then* within 3 seconds a **HIGH** alert appears in the console citing rule `R-COMBO-01`, quoting both messages, with "Call within 4 hours".
- *And* the patient receives the `escalate_notified` template in Telugu.

**US-04 Emergency symptom** (FR-10, SR-5)
- *When* the patient reports chest pain (any language), *then* the `emergency_advice` template is sent immediately and a **CRITICAL** alert is created with `due_by` ≤ 15 minutes.

**US-05 Unclear message** (SR-2)
- *When* extraction confidence < 0.6 or the patient asks a medical question, *then* no clinical answer is given; the patient gets a deferral/clarify template and a LOW "needs review" alert is created.

**US-06 Nutrition tip** (FR-14)
- *Given* a patient with diabetes and hypertension, *when* the morning check-in completes, *then* the patient receives one food tip using local foods in their language, avoiding foods flagged `limit/avoid` for their conditions.

**US-07 Audit** (FR-21, SR-8)
- *When* a clinician opens an alert, *then* they can see rule id, rule version, the facts evaluated, and source message ids.

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Patient message → reply ≤ 3 s with mock AI, ≤ 8 s with real LLM; alert visible in console ≤ 2 s after creation |
| Reliability | Demo path works with no network (mock provider); every external call has timeout + fallback |
| Safety | SR-1 to SR-9 in `CLAUDE.md` |
| Privacy | Synthetic data; PHI never in logs; consent recorded; data-minimal (docs/08) |
| Accessibility | WCAG AA; Telugu/Hindi fonts load; touch targets ≥ 44 px; no colour-only signals |
| Browser | Latest Chrome/Edge/Safari; mobile width ≥ 360 px for simulator, ≥ 1024 px for console |
| Observability | Request ids; structured logs without PHI; `/health` endpoint |
| Maintainability | Provider interfaces, config via env, tests for rule engine and validators |

## 9. Success metrics

**Prototype (what judges see)**
- End-to-end hero demo (US-03) completes in under 2 minutes, three times in a row.
- 100% of critical-symptom utterances in the eval set (`seed/eval_utterances.json`) escalate.
- Rule golden tests: 100% pass.
- Reply validator blocks 100% of seeded unsafe outputs.

**Pilot (what we would measure with a real partner)**
- 30-day readmission rate vs baseline; medicine adherence; time from red flag to clinician action; patient-reported understanding; clinician minutes per discharge.
- Targets are hypotheses, not results.

## 10. Scope and cut line

- **Demo-critical (must ship):** FR-01…FR-15, FR-21, FR-22.
- **Polish (should):** FR-16, FR-18, FR-19, FR-20.
- **Stretch (could):** FR-17, FR-23, FR-24.
- If time runs short, drop in this order: FR-24 → FR-23 → FR-17 → FR-16 → FR-20 → FR-19.

## 11. Assumptions

1. Initial scope is diabetes + hypertension only.
2. Clinic is a single demo clinic; one clinician login is enough.
3. Time zone is Asia/Kolkata; check-ins at 08:00 and 19:00.
4. Thresholds in the rule pack are **placeholders** until a clinician approves them.
5. Telugu/Hindi strings are drafts until a native speaker reviews them.
6. Nutrition data is qualitative and must be validated by a registered dietitian before any real use.

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| LLM unavailable or slow during demo | Demo fails | Mock provider default; pre-recorded backup video |
| Wrong extraction of a symptom | Missed escalation | Fail-safe upward, controlled vocabulary, eval set with 100% critical recall |
| Unreviewed medical content | Credibility, harm | Clinician-review flags, fixed templates, no advice from model |
| Scope creep | Unfinished prototype | Cut line in §10, phase plan in docs/09 |
| WhatsApp approval delays | Channel stretch fails | Simulator is the primary channel |
| Judges doubt realism | Lower score | Be explicit: synthetic data, hypotheses not results |

## 13. Open questions

1. Which clinician will review and sign the rule pack for the pitch?
2. Which languages beyond Telugu/Hindi/English, if any, for the demo?
3. Is a live WhatsApp demo desired, or is the simulator enough?
4. Deployment target for the demo (local laptop vs hosted)?
