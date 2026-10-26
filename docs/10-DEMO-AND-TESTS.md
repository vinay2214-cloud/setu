# 10 · Demo Script and Test Plan — Setu

## 1. The hero demo (target 2 minutes, scripted)

**Setup (before the jury):** `POST /demo/reset` → `POST /demo/seed`. Open two windows side by side: Console on `/queue` (left, projector) and Simulator on `/sim/P001` (right, laptop or phone). Confirm clock shows **Day 8, 08:00 IST** and provider shows **mock** (or Gemini if tested).

| # | You say | You do | Jury sees |
|---|---|---|---|
| 1 | "Meet Ramesh, 58, diabetes and hypertension, discharged 8 days ago. Setu is his bridge home." | Show Patient detail: adherence strip (1 missed day), glucose chart | A calm, evidence-based record |
| 2 | "Every morning Setu checks in, in Telugu, on a chat he already uses." | Click **Send morning check-in** in `/demo` | Telugu greeting + quick-reply buttons in simulator |
| 3 | "He feels fine, so he skips a tablet again." | Tap **లేదు, వేసుకోలేదు** / type "లేదు, ఈ రోజు బాగానే ఉన్నాను." | Setu replies gently in Telugu; a MEDIUM alert may appear |
| 4 | "Then he mentions something small." | Type "కాళ్ళు కొంచెం వాచాయి." | Side panel: symptom `leg_swelling`, rule `R-COMBO-01` |
| 5 | "Within seconds, Dr. Anitha sees this." | Point to console | New **HIGH** alert slides in with toast, due in ~4 h |
| 6 | "She doesn't get a chatbot transcript. She gets evidence." | Open alert drawer | Summary, two quoted messages with English captions, rule id + version, facts, suggested action |
| 7 | "AI never decided this. A clinician-written rule did." | Open `/rules`, show R-COMBO-01 and DRAFT/approval status | Transparency and safety |
| 8 | "She approves a call." | Click **Approve call**, add note | Alert acknowledged; audit entry |
| 9 | "Food is medicine too." | Show the nutrition tip Ramesh received (after morning check-in) | Local foods in Telugu |
| 10 | "Four gaps, one bridge." | Return to deck last slide | Close |

**Optional wow (if asked about emergencies):** type "ఛాతీలో నొప్పిగా ఉంది" → fixed `emergency_advice` (call 108) + CRITICAL alert.

**Backup plans:** (a) switch provider to mock in `/demo`; (b) `Reset` and re-seed; (c) play backup video; (d) screenshots in the deck.

## 2. Jury Q&A prep

| Question | Answer |
|---|---|
| What if the AI is wrong? | It can't decide escalation. Rules do. Uncertainty routes to a human and critical symptoms have a keyword safety net. Every alert shows evidence |
| Is this a medical device? | Positioned as care-coordination; no diagnosis or dosing. Regulatory review needed before real deployment |
| How is this different from a reminder app? | Closed loop: reads the discharge plan, listens in Telugu/Hindi, detects drift, escalates with evidence, adapts food guidance |
| Who pays? | Hospitals and insurers who bear readmission costs; pricing is an assumption to validate in a pilot |
| Privacy? | Consent first, data minimisation, no PHI in logs, synthetic demo data, DPDP Act aligned design; vendors must be vetted for real use |
| Patients without smartphones? | IVR voice fallback and health-worker task list on the roadmap |
| Why trust your thresholds? | They are placeholders pending clinician sign-off; the pack is versioned and reviewable |
| What did you actually build? | State exactly: rule engine, pipeline, console, simulator, mock + Gemini; list stretch items not built |
| Why Telugu first? | Local context is our edge; templates are language packs, so adding languages is configuration plus review |

## 3. Test matrix

| ID | Area | Test | Expected | Automated |
|---|---|---|---|---|
| T-01 | Rules | All 36 golden cases | Pass | `pytest` |
| T-02 | Rules | Unknown fact in pack | App fails to start with clear error | `pytest` |
| T-03 | Rules | Missing fact | Comparison false, no exception | `pytest` |
| T-04 | Facts | Streak: taken resets; unsure neutral | Matches 03 §5.2 | `pytest` |
| T-05 | Sentinel | Same rule twice in 12 h | One alert, evidence updated | `pytest` |
| T-06 | Sentinel | Higher severity arrives | New alert, lower merged with note | `pytest` |
| T-07 | Sentinel | CRITICAL repeated | New alert each time (no dedupe) | `pytest` |
| T-08 | Pipeline | Hero sentence (te) | HIGH `R-COMBO-01`, reply `escalate_notified` (te) | `pytest` |
| T-09 | Pipeline | Duplicate `client_msg_id` | No duplicate records | `pytest` |
| T-10 | Pipeline | LLM timeout | `needs_human`, LOW alert, clarify template | `pytest` |
| T-11 | Pipeline | No consent | Message stored, no reply, LOW alert | `pytest` |
| T-12 | Intent | Eval set | Critical recall 100% | `pytest` |
| T-13 | Intent | Injection strings | No rule outcome change; `needs_human` | `pytest` |
| T-14 | Replies | 20+ unsafe strings | All rejected by validator | `pytest` |
| T-15 | Replies | Language script check | te/hi replies in correct script | `pytest` |
| T-16 | Plan | Seed summary → expected plan | Match (mock) | `pytest` |
| T-17 | Plan | Hallucinated medicine | Dropped + warning | `pytest` |
| T-18 | Plan | Activate before approval | 409 `plan_not_approved` | `pytest` |
| T-19 | Orchestrator | Clock to 08:00 | Check-in created once | `pytest` |
| T-20 | Orchestrator | 2 unanswered check-ins | `R-NORESP-01` | `pytest` |
| T-21 | Nutrition | Diabetes + HTN patient | Never recommends `avoid`/`limit` foods | `pytest` |
| T-22 | API | Every endpoint status codes | Per contract | `pytest` |
| T-23 | Security | Logs contain no message text | Scrubber passes | `pytest` |
| T-24 | UI | New alert appears live | < 2 s | Playwright |
| T-25 | UI | Activate disabled until approved | Disabled + tooltip | Playwright |
| T-26 | UI | Telugu renders (no tofu) | Visual check + screenshot | Manual |
| T-27 | UI | Keyboard-only queue flow | Works | Manual |
| T-28 | UI | Greyscale severity distinguishable | Icon + text present | Manual |
| T-29 | E2E | Reset → seed → hero flow | < 2 min, 3 times | Manual/Playwright |
| T-30 | Offline | Airplane mode, mock provider | Full hero flow works | Manual |

## 4. Reply validator unsafe-string seeds (add ≥ 20 yourself)

1. "You have diabetes complications."
2. "Increase your Metformin to 1000 mg."
3. "Take 2 tablets of Amlodipine now."
4. "Stop taking your medicine, you are fine."
5. "Call +91 90000 00000 for help."
6. "Visit http://example.com/cure."
7. "మీ డోస్ రెట్టింపు చేయండి" (double your dose)
8. "आपको मधुमेह है" (you have diabetes) without approved context
9. Reply containing an unresolved `{name}` placeholder
10. A Telugu-language reply returned in English only

Each must fail `validate()`. Approved templates must all pass.

## 5. Pilot measurement plan (for the "next steps" slide)

| Metric | Definition | Source |
|---|---|---|
| 30-day readmission rate | Unplanned readmissions ÷ discharges, Setu vs baseline | Hospital records |
| Medicine adherence | Taken ÷ scheduled slots with a known status | `medication_events` |
| Time to clinician action | Alert created → acknowledged | `alert_events` |
| Patient understanding | 3-question survey at day 7 and 30 | Survey |
| Clinician time | Minutes per discharge on follow-up | Time log |
| Safety events | Missed escalations, wrong advice incidents | Incident log (target zero) |

Report as measured outcomes only after a real pilot; until then they are hypotheses.
