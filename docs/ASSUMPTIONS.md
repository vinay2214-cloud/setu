# Assumptions and Decisions Log

Add a line whenever you assume something, resolve a doc conflict, or reuse outside code. Newest first.

| Date | Area | Assumption / decision | Why | Owner |
|---|---|---|---|---|
| 2026-10-26 | Scope | Prototype covers diabetes + hypertension only | Fits the pitch and keeps rule pack reviewable | Team |
| 2026-10-26 | Channel | Simulator is the primary channel; WhatsApp adapter is stretch | Removes approval dependency from the demo | Team |
| 2026-10-26 | AI | `mock` provider is the default; Gemini optional | Offline-safe demo | Team |
| 2026-10-26 | Rules | All thresholds are placeholders pending clinician review | Safety and honesty | Team |
| 2026-10-26 | Content | Telugu/Hindi strings and food suitability are drafts | Need native speaker and dietitian review | Team |
| 2026-10-26 | Pricing | ₹150 per patient per month is an assumption | Validate in pilot | Team |

## Open items for a human
- [ ] Which clinician reviews the rule pack, and when?
- [ ] Native-speaker review of Telugu and Hindi templates
- [ ] Dietitian review of `foods_andhra.json`
- [ ] Decide: live WhatsApp demo or simulator only?
- [ ] Confirm deployment plan (local vs hosted)
