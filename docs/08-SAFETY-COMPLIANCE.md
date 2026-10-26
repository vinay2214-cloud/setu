# 08 · Safety, Privacy and Compliance — Setu

> This is an engineering and product safety plan for a **hackathon prototype**. It is not legal or clinical advice. Before any real patient use, obtain clinical governance sign-off and legal review.

## 1. Positioning

Setu is a **care-coordination and monitoring support tool**. It does not diagnose, prescribe, or change treatment. Clinicians remain responsible for every clinical decision. Keep this wording in the UI footer, deck, and README. If the product were to claim diagnostic or treatment-decision functions, it could fall under medical-device regulation (e.g. India's Medical Devices Rules, 2017) and would need a regulatory assessment.

## 2. Hazard analysis

| ID | Hazard | Cause | Mitigation | Verified by |
|---|---|---|---|---|
| H1 | Critical symptom not escalated | LLM misses or mislabels symptom | Keyword safety net independent of LLM; fail-safe upward; critical set rule `R-CRIT-SYM-01`; eval recall 100% | `eval_intents`, golden tests |
| H2 | Wrong medicine/dose in plan | LLM hallucination | Verbatim dose copy; span verification; clinician approval gate; "AI-extracted" tags | plan compiler tests, UI checklist |
| H3 | AI gives medical advice | LLM free text to patient | Templates only for clinical keys; reply validator; no tools; `medical_question_defer` | validator unit tests (≥ 20 unsafe strings) |
| H4 | Rule threshold wrong | Placeholder numbers | All thresholds flagged `clinician_review: required`; DRAFT banner; no hard-coded numbers in code | rule pack review checklist |
| H5 | Alert fatigue | Too many LOW/MEDIUM alerts | Dedupe window, severity SLA, snooze, KPI on alerts per patient-day | metrics screen |
| H6 | Missed alert | Console not watched / SSE down | Overdue highlighting, reconnect, queue refetch, optional notification | manual test |
| H7 | Language mistranslation | Draft Telugu/Hindi strings | Native-speaker review, templates in one file, show English caption to clinician | review checklist |
| H8 | Patient has no smartphone | Digital divide | IVR/voice fallback on roadmap; health-worker task list (stretch) | deck, roadmap |
| H9 | Privacy breach | PHI in logs, public deployment | Synthetic data, PHI scrubber, env secrets, auth on console, no public real data | log tests |
| H10 | Prompt injection | Patient types instructions | Delimited data, schema-only output, no tools, rules deterministic | injection tests |
| H11 | Emergency delayed | Patient waits for chat | Fixed emergency template tells patient to call 108 / go to hospital immediately; CRITICAL SLA 15 min | template test |
| H12 | Over-trust in AI | UI hides uncertainty | Confidence badges, evidence quotes, rule provenance | UI checklist |
| H13 | Stale clock / demo artefacts | Demo clock leaks | Clock only in `DEMO_MODE`; ribbon "Synthetic demo" | config test |

## 3. Clinical content governance

1. **Rule pack** (`seed/rules/diabetes_htn_v1.yaml`) ships as `status: DRAFT`. A named clinician must review every threshold, severity, SLA and patient template, then set `status: APPROVED`, `approved_by`, `approved_at`. The UI shows this status.
2. **Patient templates** marked `clinical: true` need clinician sign-off on wording and a native-speaker check.
3. **Nutrition database** is qualitative; a registered dietitian validates `dm_suitability` and `htn_suitability` per food. Cross-check against the Indian Food Composition Tables (NIN, 2017).
4. **Emergency numbers:** 108 (ambulance) and 112 (national emergency) are used in templates; confirm local applicability for the pilot region.
5. Keep a `docs/CLINICAL_REVIEW_LOG.md` with reviewer, date, change.

### Rule pack review checklist
- [ ] Each rule's severity matches clinic's triage policy
- [ ] Thresholds match clinic protocol and units
- [ ] Rules covering critical symptoms are fail-safe
- [ ] SLA minutes are achievable by the clinic
- [ ] Patient-facing text contains no dose or diagnosis
- [ ] Golden test cases reflect reviewer's expectations

## 4. Privacy and data protection (India DPDP Act, 2023 — engineering view)

Principles to build in from day one (confirm legal obligations with counsel before real use):

| Principle | Implementation |
|---|---|
| Consent | Explicit, recorded consent before any message (`consents`); simple language, versioned text; revoke stops messaging |
| Purpose limitation | Data used only for care coordination; no analytics resale; no model training on patient data |
| Data minimisation | Collect only name, age, sex, language, contact, conditions, plan, readings, messages |
| Accuracy and correction | Clinician can edit plan and patient record; versioning |
| Storage limitation | Retention setting; demo reset wipes data; delete endpoint |
| Security | Secrets in env, TLS in deployment, auth, rate limits, no PHI in logs, least privilege |
| Breach readiness | Incident checklist in README (who, what, when to notify) |
| Children / guardians | Prototype excludes minors |
| Cross-border / vendors | LLM and speech vendors process text/audio; for real use select vendors with suitable agreements and data-residency terms, and prefer on-device/local models where PHI is involved |

For the hackathon: **no real PHI, ever.** Use only `seed/` data.

## 5. Consent text (v1 draft, English)

> "Setu will send you messages about your medicines, food and warning signs after you leave hospital, and will tell your care team if something looks wrong. Setu does not replace your doctor. In an emergency call 108. You can stop at any time by replying STOP or telling your care team. Your information is used only for your care."

Provide te/hi versions after native review.

## 6. UI disclaimers (exact placement)

- Console footer and simulator header: "Prototype · Synthetic data · Not for clinical use".
- Simulator first message: "I am Setu, an automated assistant. I am not a doctor. In an emergency call 108."
- Rules page: DRAFT banner while unapproved.

## 7. Security checklist (prototype)

- [ ] `.env` not committed; `.env.example` has no secrets
- [ ] JWT secret rotated from default
- [ ] CORS limited to frontend origin
- [ ] Rate limits on `/sim/messages`, `/speech/*`
- [ ] Input size limits enforced
- [ ] PHI scrubber test passes (no message text in logs)
- [ ] Demo endpoints disabled when `DEMO_MODE=false`
- [ ] Dependencies pinned (`pip freeze`, `package-lock.json`)
- [ ] No real phone numbers in code or seeds

## 8. Responsible-AI statements for the pitch

1. AI never decides who gets escalated; transparent clinician-written rules do.
2. Every alert is explainable: rule, facts, quotes.
3. Uncertainty routes to humans, not guesses.
4. Patients are told they are talking to an automated assistant.
5. Results claimed in the deck are hypotheses until a pilot measures them.

## 9. Incident and rollback (demo)

If the AI misbehaves during the demo: switch provider to **mock** in `/demo` (one click), reset data, and continue. Keep a recorded backup video of the hero flow.
