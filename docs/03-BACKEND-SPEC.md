# 03 · Backend Specification — Setu

Stack: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, APScheduler, sse-starlette, PyYAML, httpx.
All endpoints are defined in `04-API-CONTRACT.md`; tables in `05-DATA-MODEL.md`.

## 1. Module map

```
app/
  main.py            # app factory, routers, lifespan (load rules, start scheduler)
  config.py          # Settings (pydantic-settings)
  deps.py            # db session, current clinician, providers (DI)
  core/
    clock.py         # now(), advance(days), reset()  -> demo clock
    audit.py         # audit(actor, action, entity, entity_id, detail)
    security.py      # JWT helpers, demo accounts
    logging.py       # structured logs, PHI scrubber
  providers/
    llm/{base,mock,gemini}.py
    speech/{base,sarvam}.py
    channel/{base,simulator,whatsapp}.py
  services/
    plan_compiler.py
    intent_extractor.py
    fact_builder.py
    sentinel.py        # applies rule engine, dedupes, creates alerts
    summary_writer.py
    reply_composer.py  # templates + validator
    nutrition.py
    orchestrator.py    # scheduled check-ins, no-response handling
    pipeline.py        # handle_inbound_message(...)
  rules/{loader,engine}.py
  models/ schemas/ api/
```

## 2. Configuration (`config.py`)

Fields (all from `.env`, see `.env.example`): `app_env`, `database_url`, `jwt_secret`, `cors_origins`, `llm_provider` (mock|gemini), `gemini_api_key`, `gemini_model`, `speech_provider` (none|sarvam), `sarvam_api_key`, `channel_adapter` (simulator|whatsapp), WhatsApp credentials, `demo_mode`, `clinic_name`, `default_tz`, `llm_timeout_s=8`, `speech_timeout_s=6`.

## 3. Provider interfaces

```python
class LLMProvider(Protocol):
    async def generate_json(self, *, system: str, user: str, schema: dict, temperature: float = 0.0) -> dict: ...
    async def generate_text(self, *, system: str, user: str, temperature: float = 0.2) -> str: ...

class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes, mime: str, language_hint: str | None) -> TranscriptResult: ...
    async def synthesize(self, text: str, language: str) -> bytes: ...   # audio/wav or mp3

class ChannelAdapter(Protocol):
    async def send(self, patient: Patient, message: OutboundMessage) -> None: ...
    # inbound arrives via API (simulator) or webhook (whatsapp) and calls pipeline.handle_inbound_message
```

**MockLLMProvider** must be deterministic and good enough for the full demo:
- `generate_json` for intent extraction uses keyword/regex tables for te/hi/en (see docs/07 §3.4) and returns valid `IntentResult`.
- For plan compilation it returns the canned plan in `seed/discharge_summary_ramesh.expected_plan.json` when the input text matches the seed summary (hash or fuzzy match), else a minimal plan with `needs_review=true`.
- For summaries it uses a template string filled from evidence.

**GeminiProvider**: uses the `google-genai` SDK, JSON-schema constrained output where available, model from `GEMINI_MODEL`, timeout `llm_timeout_s`, one repair retry on invalid JSON.

## 4. Message pipeline — `services/pipeline.py`

```python
async def handle_inbound_message(db, patient_id: str, *, text: str | None,
                                 audio: bytes | None, language_hint: str | None,
                                 client_msg_id: str, quick_reply: str | None = None) -> PipelineResult
```

Steps (all inside one DB transaction except provider calls):

1. **Idempotency:** if `client_msg_id` exists → return the stored result.
2. **Consent check:** patient must have active consent, else store message, no reply, LOW alert "message without consent".
3. **Transcribe** if audio (SpeechProvider); keep `audio_url` and transcript; on failure → ask patient to type.
4. **Save inbound message** (`direction=in`, language, text).
5. **Translate for clinician:** `text_en` via LLM (or mock dictionary). Failure is non-fatal.
6. **Extract:** `intent_extractor.extract(text, plan, language, context)` → `IntentResult`. On failure → fallback `needs_human=true, confidence=0`.
   - `quick_reply` values (`yes_taken`, `not_taken`, `no_symptoms`, `have_symptom:<code>`) bypass the LLM and map directly (deterministic).
7. **Persist facts:** medication events (see §6), observations, symptoms; link `source_message_id`.
8. **Build facts:** `fact_builder.build(db, patient_id, now)`.
9. **Evaluate rules:** `sentinel.evaluate(db, patient, facts, trigger_message_id)` → list of `FiredRule`; dedupe and upsert alerts; write `rule_evaluations` and `audit_log`.
10. **Summarise** any new/updated alert with `summary_writer` (LLM or template); on failure use the template summary.
11. **Publish SSE** `alert.created` / `alert.updated`.
12. **Compose replies:** `reply_composer.plan(...)` → ordered template keys; render in patient language; validate; save as outbound messages; send via ChannelAdapter.
13. **Return** `PipelineResult { replies[], alerts[], extracted }`.

### Reply planning rules (deterministic, in order)
1. Any CRITICAL fired rule → `emergency_advice` (or `glucose_low_advice` if glucose rule) **only**, then `escalate_notified`.
2. Any HIGH/MEDIUM fired rule → `escalate_notified`.
3. For each medication event: taken → `ack_taken`; missed → `ack_missed_gentle`.
4. For each vital recorded → `ack_vital`.
5. If a meal was reported → `meal_feedback_good` / `meal_feedback_limit` via nutrition engine.
6. If `question.category == medical` → `medical_question_defer`.
7. If `needs_human` or confidence < 0.6 and nothing else matched → `unclear_ask_again`.
8. If check-in just completed (all prompts answered) → `nutrition_tip` then `closing`.
9. Max 3 messages per turn; priority order as above.

## 5. Rule engine — `rules/`

### 5.1 Pack format
See `seed/rules/diabetes_htn_v1.yaml`. Each rule: `id`, `title`, `severity`, `when` (condition tree), `suggested_action`, `patient_template`, `sla_minutes`, `rationale`, `clinician_review`.

Condition tree:
```yaml
when:
  all:                                # or: any: / not:
    - {fact: symptoms, op: contains_any, value: [leg_swelling]}
    - {fact: max_missed_streak_critical, op: ">=", value: 2}
```
Operators: `==, !=, >, >=, <, <=, in, not_in, contains_any, contains_all, is_true, is_false`. A missing fact (`None`) makes `>`/`<` style comparisons **false**, never an error. Unknown fact names raise at load time (fail fast).

### 5.2 Facts (built by `fact_builder`)
| Fact | Type | Definition |
|---|---|---|
| `conditions` | set[str] | From care plan diagnoses mapped to `diabetes`, `hypertension` |
| `days_since_discharge` | int | Calendar days, from demo clock |
| `max_missed_streak_critical` | int | Max over medicines with `criticality=critical` of consecutive most-recent scheduled days with status `missed`. A day with `taken` resets to 0. `unsure`/no data neither extends nor resets |
| `symptoms` | set[str] | Non-negated symptom codes reported in the last 24 h |
| `symptom_severity_unknown_critical` | bool | A critical-set symptom reported without clear severity (fail-safe, treated as true critical) |
| `glucose_latest` | float \| None | Latest mg/dL reading in last 12 h |
| `glucose_context` | str \| None | fasting / random / unknown |
| `bp_sys_latest`, `bp_dia_latest` | int \| None | Latest BP in last 24 h |
| `consecutive_no_response` | int | Count of most recent check-ins with status `missed` |
| `intent_confidence_min` | float | Min confidence of the triggering message (1.0 if no message) |
| `needs_human` | bool | From IntentResult |
| `medical_question` | bool | IntentResult question.category == medical |

### 5.3 Evaluation
```python
class FiredRule(BaseModel):
    rule_id: str; rule_version: str; severity: Severity
    facts_used: dict[str, Any]; evidence_message_ids: list[str]; due_by: datetime
```
- Evaluate **all** rules; return all that fire (sorted by severity desc).
- Every evaluation (fired or not) is stored in `rule_evaluations` only when at least one rule fires, plus a compact "no rule fired" record per message for audit.
- Severity order: `LOW < MEDIUM < HIGH < CRITICAL`.

### 5.4 Family reduction, dedupe and merge
1. **Family reduction (engine):** each rule has a `family`. Within one evaluation only the highest-severity fired rule per family is kept (e.g. `R-COMBO-01` replaces `R-SWELL-01`).
2. **One alert per patient per evaluation (sentinel):** after family reduction, the **highest-severity** fired rule becomes the *primary* rule of the alert. The other fired rules are stored as `contributing_rules` (shown in the UI as flags). Ties are broken by rule id order in the pack.
3. **Dedupe:** if the patient already has an open/acknowledged alert whose primary rule is the same, within `dedupe_window_hours` for its severity (CRITICAL = 0, so always new), **update** that alert (evidence, facts, contributing rules, `updated_at`) instead of creating another.
4. **Upgrade and merge:** if the new primary severity is **higher** than the patient's current open alert, create a new alert, link it with `related_alert_id`, and **close the older, lower-severity alert** with `resolution_note = "merged into <new id>"` (alert event `merged`). If the older alert's rule is still firing, include it in the new alert's `contributing_rules`.
5. **Hero example:** step 2 creates a MEDIUM alert (`R-ADH-01`). Step 3 (swelling) fires `R-ADH-01` + `R-COMBO-01`; `R-COMBO-01` is HIGH, so a new HIGH alert is created with `contributing_rules=[R-ADH-01]` and the MEDIUM alert is merged into it. The clinician sees **one** HIGH alert with two flags.

### 5.5 SLA
`due_by = now + sla_minutes` where defaults are CRITICAL 15, HIGH 240, MEDIUM 1440, LOW 4320.

### 5.6 Testing
`seed/rules/diabetes_htn_v1.tests.json` holds golden cases (facts → expected fired rule ids). The test suite loads the pack, runs each case, and asserts equality of the **set** of fired ids. These tests are mandatory in CI.

## 6. Medication tracking

- When a plan is activated, the orchestrator materialises **scheduled slots** (`morning`, `noon`, `evening`, `bedtime`) per medicine per day from `frequency_code` and `times`:
  `OD` morning (or as `times`), `BD` morning+evening, `TDS` morning+noon+evening, `HS` bedtime.
- A patient statement maps to slots by time of day of the check-in (morning check-in → morning slot).
- "Yes, taken" without specifics marks all medicines for that check-in's slot as `taken`.
- If the patient names a medicine, only that medicine is updated; the others remain `unknown` until answered.
- Statuses: `taken`, `missed`, `unsure`, `unknown`. Only `missed` counts for streaks.

## 7. Orchestrator — `services/orchestrator.py`

- APScheduler job runs every 30 s (real time) and calls `tick()`.
- `tick()` finds active plans where a check-in is due by `clock.now()` and not yet created → creates `check_ins` rows and sends the prompt sequence (greeting → medicines with quick replies → glucose → symptoms).
- Marks a check-in `missed` if unanswered 3 h after send (clock-based), then re-evaluates `consecutive_no_response` rules.
- `advance(days)`: moves the demo clock forward by N days, then runs `tick()` repeatedly day by day so that history accrues (used by `POST /demo/time-travel`).
- All check-ins use the patient's language and name; first check-in is the day after activation.

## 8. Nutrition engine — `services/nutrition.py`

Inputs: conditions, plan diet restrictions, `seed/foods_andhra.json` (`foods`, `tip_pairs`, `add_tips`), patient language, reported meal text, recent tips.
Tip sources: `nutrition_tip_swap` uses a `tip_pairs` entry (`limit` food → one of its `prefer` foods); `nutrition_tip_add` uses an `add_tips` food. Filter every candidate through the allowed set below.

```python
def daily_tip(patient, plan, foods, history) -> NutritionTip   # {text_key, params, food_ids}
def feedback_for_meal(patient, foods, extracted_foods) -> MealFeedback  # {good:[ids], limit:[ids]}
```
Algorithm:
1. Build allowed set: foods where `dm_suitability` not in `{avoid}` if `diabetes` in conditions and `htn_suitability` not in `{avoid}` if `hypertension` in conditions.
2. Prefer items where suitability is `prefer` for each condition; skip foods used in the last 3 tips; respect plan restrictions (e.g. "low salt").
3. A tip is a **swap**: pick a commonly eaten `limit` food from the patient's reported meals (or a default like `white_rice_large`) and pair it with a `prefer` alternative in the same `category` (breakfast→breakfast, staple→staple). Render via `nutrition_tip_swap` template.
4. **Never output quantities, calories, or medical claims.** Text is limited to the template with localised food names.
5. Meal feedback: match extracted foods to DB by `aliases` (case-insensitive, Telugu script supported); unknown foods are ignored.

## 9. Plan compiler — `services/plan_compiler.py`

- Input: raw discharge text, patient language. Output: `CarePlanDraft` (schema in docs/05 §4).
- Each medicine/diagnosis/monitoring item carries `source_span: {start, end, text}` and `confidence` (0–1).
- Any item with confidence < 0.75 or missing dose text gets `needs_review=true` (UI highlights).
- **Doses are copied verbatim** (`dose_text`) — never normalised, converted, or calculated.
- Validation: reject items whose `source_span.text` cannot be found in the input (anti-hallucination); drop them and add a `warnings[]` entry.
- Versioning: every clinician edit creates `version+1` with a diff stored in `audit_log`.
- Activation guard: `status` must be `approved`; approver recorded.

## 10. Summary writer — `services/summary_writer.py`

- Input: alert, fired rules, facts, up to 5 evidence messages (translated text_en + original).
- Output: ≤ 60 words, plain English, **must reference only provided evidence**; template fallback:
  `"{age}{sex}, day {day} post-discharge. {rule_titles}. Latest: {latest_quote}."`
- Post-check: reject outputs containing diagnosis words, numbers not present in facts, or drug names not in plan; fallback to template.

## 11. SSE

`GET /api/v1/alerts/stream` emits events (`alert.created`, `alert.updated`, `alert.resolved`, `check_in.sent`, `demo.clock`) as JSON. Use an in-process `asyncio.Queue` broadcaster (fine for a single-process prototype). Send a `ping` every 15 s.

## 12. Security (prototype level)

- Demo accounts seeded: `dr.anitha@demo.setu` / `demo123` (clinician), `admin@demo.setu` / `demo123` (admin). Passwords hashed (bcrypt via `passlib` or `hashlib.scrypt`).
- JWT (HS256) 8 h, httpOnly cookie, SameSite=Lax. Simulator uses `X-Sim-Token` with `patient_id` claim.
- Rate limit (in-memory) 30 req/min per IP on `/sim/messages` and `/speech/*`.
- Input limits: message ≤ 1000 chars, audio ≤ 1 MB / 30 s.
- Logging: structured JSON; PHI scrubber drops `text`, `name`, `phone`.

## 13. Errors

Uniform error body (see API contract §2). Never leak stack traces. Map provider errors to 502 with a safe message; pipeline errors after message save still return 200 with `needs_review` and create a LOW alert.

## 14. Tests (pytest)

| Area | Must test |
|---|---|
| Rule engine | All golden cases; unknown fact fails load; missing fact is false |
| Fact builder | Streak calculation (taken resets, unsure neutral), symptom windowing |
| Sentinel | Dedupe, severity upgrade, SLA times |
| Reply composer | Priority order, max 3 messages, validator blocks unsafe text |
| Pipeline | Hero scenario (US-03) end to end with mock provider |
| Intent (mock) | Eval set `seed/eval_utterances.json`: 100% critical symptom recall |
| Plan compiler | Seed summary → expected plan; hallucinated span dropped |
| API | Contract tests for every endpoint status code |
| Orchestrator | Check-ins created at 08:00/19:00 clock times; no-response marking |

## 15. Performance and limits (prototype)

Single process, SQLite. Target < 200 ms for non-AI endpoints, < 3 s message pipeline with mock AI. No background workers beyond APScheduler.
