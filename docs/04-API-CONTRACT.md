# 04 · API Contract — Setu

Base URL: `http://localhost:8000/api/v1` · Content type: JSON (UTF-8) · Times: ISO 8601 UTC (`2026-10-26T02:30:00Z`); the UI displays Asia/Kolkata.
The backend must expose `/openapi.json`; the frontend generates types from it. **This document wins any disagreement.**

## 1. Conventions

- **Auth:** clinician endpoints require cookie `setu_session` (JWT). Simulator endpoints require header `X-Sim-Token: <token>` obtained from `POST /sim/session`.
- **IDs:** `P001` patient, `CP-0001` care plan, `A-0001` alert, `M-xxxxxxxx` message, `CI-xxxxxxxx` check-in, `DOC-0001` document.
- **Enums:**
  - `language`: `te` | `hi` | `en`
  - `severity`: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`
  - `alert.status`: `open` | `acknowledged` | `snoozed` | `resolved`
  - `plan.status`: `draft` | `approved` | `active` | `completed`
  - `med.status`: `taken` | `missed` | `unsure` | `unknown`
- **Pagination:** `?limit=50&cursor=<opaque>`; responses `{ "items": [...], "next_cursor": "..." | null }`.

## 2. Error format

```json
{ "error": { "code": "plan_not_approved", "message": "Care plan must be approved before activation.", "request_id": "req_8f2c" } }
```
Codes: `validation_error` (422), `not_found` (404), `unauthorized` (401), `forbidden` (403), `plan_not_approved` (409), `consent_missing` (409), `rate_limited` (429), `provider_error` (502), `internal_error` (500).

## 3. Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/login` | `{ "email", "password" }` | `200 { "clinician": {id, name, role} }` + cookie |
| POST | `/auth/logout` | — | `204` |
| GET | `/auth/me` | — | `200 { id, name, role, clinic }` |

## 4. Patients

| Method | Path | Notes |
|---|---|---|
| GET | `/patients` | Query `status`, `q`. Returns list with `risk` summary |
| POST | `/patients` | Create + consent |
| GET | `/patients/{id}` | Detail |
| DELETE | `/patients/{id}` | Demo reset only (`DEMO_MODE=true`) |
| GET | `/patients/{id}/timeline` | Observations, symptoms, med events, check-ins, alerts, merged and sorted desc |
| GET | `/patients/{id}/adherence?days=14` | Per-day, per-medicine status |
| GET | `/patients/{id}/vitals?type=glucose&days=14` | Series |
| GET | `/patients/{id}/messages` | Conversation, newest last |
| GET | `/patients/{id}/fhir` | (stretch) FHIR R4 Bundle |

**POST /patients — request**
```json
{
  "name": "Ramesh Kumar", "age": 58, "sex": "M", "language": "te",
  "phone": "+910000000001", "location": "Vijayawada",
  "conditions": ["diabetes", "hypertension"],
  "discharge_date": "2026-10-18",
  "consent": { "type": "care_messaging", "channel": "whatsapp", "text_version": "v1", "granted": true }
}
```
**Patient object**
```json
{
  "id": "P001", "name": "Ramesh Kumar", "age": 58, "sex": "M", "language": "te",
  "location": "Vijayawada", "conditions": ["diabetes","hypertension"],
  "discharge_date": "2026-10-18", "day_since_discharge": 8,
  "status": "active",
  "plan": { "id": "CP-0001", "status": "active", "version": 2 },
  "risk": { "open_alerts": 1, "highest_severity": "HIGH", "adherence_7d": 0.78, "last_response_at": "2026-10-26T02:30:00Z" }
}
```
`GET /patients` sorts by `risk.highest_severity` desc, then oldest open alert.

## 5. Documents and care plans

| Method | Path | Notes |
|---|---|---|
| POST | `/patients/{id}/documents` | `{ "kind": "discharge_summary", "text": "..." }` → `201 { id }` |
| POST | `/patients/{id}/care-plans/draft` | `{ "document_id" }` → `201 CarePlan(status=draft)` (runs PlanCompiler) |
| GET | `/care-plans/{id}` | Includes `source_text` and spans |
| PATCH | `/care-plans/{id}` | Clinician edits `plan` JSON → new version |
| POST | `/care-plans/{id}/approve` | `{ "note": "" }` → status `approved` |
| POST | `/care-plans/{id}/activate` | Requires approved; creates schedule → `active` |
| GET | `/patients/{id}/care-plans` | Versions list |

**CarePlan object** (shape in `05-DATA-MODEL.md §4`)
```json
{
  "id": "CP-0001", "patient_id": "P001", "version": 1, "status": "draft",
  "plan": { "...": "CarePlanJson" },
  "warnings": ["Dropped item 'Aspirin 75mg': source text not found."],
  "created_at": "...", "approved_by": null, "approved_at": null
}
```

## 6. Simulator and messaging

| Method | Path | Notes |
|---|---|---|
| POST | `/sim/session` | `{ "patient_id" }` → `{ "token", "patient": {id, name, language} }`; requires consent and persists the fixed disclaimer once |
| POST | `/sim/messages` | Header `X-Sim-Token`; `{ "patient_id", "client_msg_id", "text", "language", "quick_reply" }`; duplicate `client_msg_id` returns the exact original response snapshot |
| GET | `/sim/messages?patient_id=P001&after=<msg_id>&limit=50` | Header `X-Sim-Token`; poll up to 100 outbound messages; response includes `next_after` when more remain |
| GET | `/sim/stream?patient_id=P001` | Header `X-Sim-Token`; patient-scoped SSE (`message.created`) |

**POST /sim/messages — request**
```json
{
  "patient_id": "P001",
  "client_msg_id": "c-7d1a",
  "text": "కాళ్ళు కొంచెం వాచాయి",
  "language": "te",
  "quick_reply": null
}
```
**Response**
```json
{
  "message": { "id": "M-1a2b3c4d", "direction": "in", "text": "కాళ్ళు కొంచెం వాచాయి", "text_en": "My feet are a bit swollen", "language": "te", "created_at": "..." },
  "replies": [
    { "id": "M-2b3c4d5e", "direction": "out", "template_key": "escalate_notified", "text": "మీ డాక్టర్ గారికి తెలియజేశాను. కేర్ టీమ్ నుంచి త్వరలో మిమ్మల్ని సంప్రదిస్తారు.", "text_en": "I have informed your doctor. ...", "language": "te", "quick_replies": [] }
  ],
  "alerts": [ { "id": "A-0007", "severity": "HIGH", "rule_id": "R-COMBO-01", "status": "open" } ],
  "extracted": { "intents": ["symptom_report"], "symptoms": [{"code":"leg_swelling","negated":false}], "confidence": 0.93, "needs_human": false }
}
```
`quick_replies` in a message: `[{ "id": "yes_taken", "label": "అవును, వేసుకున్నాను" }, ...]`. Quick reply ids: `yes_taken`, `not_taken`, `no_symptoms`, `have_symptom`, `skip`.

An idempotent retry does not rerun extraction or create new messages, events, or alerts. New messages persist and replay the original response, including alert summaries at the time of processing. For a legacy inbound message without a snapshot, its first retry reconstructs and stores a best-effort response from the existing records; subsequent retries replay that snapshot.

**Message object**
```json
{ "id":"M-...", "patient_id":"P001", "direction":"in|out", "channel":"simulator|whatsapp",
  "language":"te", "text":"...", "text_en":"...", "audio_url":null,
  "template_key":null, "intent": null, "created_at":"..." }
```

## 7. Alerts

| Method | Path | Notes |
|---|---|---|
| GET | `/alerts` | Query `status` (default `open,acknowledged`), `severity`, `patient_id`; sorted severity desc then `due_by` asc |
| GET | `/alerts/{id}` | Full detail |
| POST | `/alerts/{id}/acknowledge` | `{ "note": "" }` |
| POST | `/alerts/{id}/snooze` | `{ "minutes": 120, "note": "" }` |
| POST | `/alerts/{id}/resolve` | `{ "note": "Called patient; advised clinic visit" }` (note required) |
| POST | `/alerts/{id}/approve-call` | Marks "call approved", assigns to clinician/health worker; `{ "assignee": "dr.anitha", "note": "" }` |
| GET | `/alerts/stream` | SSE |
| GET | `/alerts/metrics` | KPI strip: `{ open, by_severity, median_minutes_to_ack_7d, overdue }` |

**Alert object**
```json
{
  "id": "A-0007", "patient": { "id":"P001", "name":"Ramesh Kumar", "age":58, "sex":"M", "language":"te", "day_since_discharge":8 },
  "severity": "HIGH", "status": "open",
  "title": "Missed dose ×2 with new leg swelling",
  "summary": "58M, day 8 post-discharge. Missed critical medicines two days running and reports leg swelling today. Latest: \"My feet are a bit swollen\".",
  "rule": { "id": "R-COMBO-01", "version": "1.0.0", "title": "Leg swelling with repeated missed doses", "clinician_review": "required" },
  "facts_used": { "max_missed_streak_critical": 2, "symptoms": ["leg_swelling"] },
  "contributing_rules": [ { "id": "R-ADH-01", "version": "1.0.0", "title": "Critical medicines missed 2 days running", "severity": "MEDIUM" } ],
  "related_alert_id": "A-0006",
  "evidence": [
    { "message_id": "M-1a2b", "at": "...", "text": "లేదు, ఈ రోజు బాగానే ఉన్నాను.", "text_en": "No, I'm feeling fine today.", "language": "te" },
    { "message_id": "M-2b3c", "at": "...", "text": "కాళ్ళు కొంచెం వాచాయి.", "text_en": "My feet are a bit swollen.", "language": "te" }
  ],
  "suggested_action": "Call within 4 hours",
  "due_by": "2026-10-26T06:30:00Z", "created_at": "...", "updated_at": "...",
  "acknowledged_by": null, "resolved_at": null, "snoozed_until": null,
  "events": [ { "at":"...", "actor":"system", "action":"created", "note":"" } ]
}
```

**SSE events** (`GET /alerts/stream`, `text/event-stream`)
```
event: alert.created
data: {"alert": { ...Alert }}

event: alert.updated
data: {"alert": { ...Alert }}

event: demo.clock
data: {"now": "2026-10-26T02:30:00Z", "day_offset": 8}

event: ping
data: {}
```

## 8. Rules (read-only)

| Method | Path | Response |
|---|---|---|
| GET | `/rules/packs` | `[ { id, name, version, status, approved_by, approved_at, rule_count } ]` |
| GET | `/rules/packs/{id}` | Pack with rules (id, title, severity, human-readable condition, sla_minutes, rationale, clinician_review) |
| POST | `/rules/evaluate` | (dev only) `{ "facts": {...} }` → fired rules; used by tests and the demo panel |

## 9. Speech (optional)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/speech/transcribe` | multipart `audio`, `language_hint` | `{ "text", "language", "confidence" }` |
| POST | `/speech/synthesize` | `{ "text", "language" }` | `audio/wav` stream |

## 10. Demo control (`DEMO_MODE=true` only)

| Method | Path | Body | Effect |
|---|---|---|---|
| POST | `/demo/seed` | `{ "scenario": "default" }` | Loads `seed/patients.json`, plan(s), history; sets clock to scenario start |
| POST | `/demo/reset` | — | Drops and recreates all data, resets clock |
| POST | `/demo/time-travel` | `{ "days": 1, "hours": 0 }` | Advances clock, runs orchestrator ticks |
| POST | `/demo/check-in` | `{ "patient_id", "kind": "morning" }` | Sends check-in immediately |
| POST | `/demo/scenario-step` | `{ "patient_id", "step": 3 }` | Applies scripted patient messages from `seed/scenario_ramesh.json` |
| GET | `/demo/state` | — | `{ now, llm_provider, speech_provider, channel }` |
| POST | `/demo/providers` | `{ "llm": "mock" }` | Switch provider at runtime |

## 11. Webhooks (stretch)

| Method | Path | Notes |
|---|---|---|
| GET | `/webhooks/whatsapp` | Meta verification (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| POST | `/webhooks/whatsapp` | Inbound messages and status updates; verify signature; call pipeline; remember WhatsApp's 24-hour customer-service window for free-form replies |

## 12. Health

`GET /health` → `{ "status":"ok", "db":"ok", "rules_loaded": 22, "llm":"mock", "time":"..." }`

## 13. Status codes summary

200 OK · 201 Created · 204 No Content · 401 / 403 auth · 404 not found · 409 state conflict (plan not approved, consent missing) · 422 validation · 429 rate limit · 502 provider failure.
