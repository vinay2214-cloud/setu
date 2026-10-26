# Assumptions and Decisions Log

Add a line whenever you assume something, resolve a doc conflict, or reuse outside code. Newest first.

| Date | Area | Assumption / decision | Why | Owner |
|---|---|---|---|---|
| 2026-10-26 | Simulator idempotency | Persist the original `/sim/messages` response snapshot on the inbound message, add the column at startup on SQLite/PostgreSQL, and snapshot a best-effort reconstruction on the first replay of a legacy message | Duplicate POSTs must not rerun extraction or return a different alert snapshot after later events | Codex |
| 2026-10-26 | Demo alerts | P002/P003/P005 are seeded as open, rule-backed alerts from their fixture summaries; where no original message exists, `evidence_json` stays empty and the audit entry records the fixture reference and an empty `source_message_ids` list | Preserves provenance without inventing patient messages | Codex |
| 2026-10-26 | Mock extraction | P2 uses deterministic keyword and numeric patterns for the offline provider; unsupported language forms become `needs_human`, and critical recall is gated against the checked-in evaluation utterances | Keeps offline behavior predictable while real-provider support remains optional | Codex |
| 2026-10-26 | Backend models | SQLAlchemy mappings are reflected from `backend/db/schema.sql` at startup | Keeps the checked-in SQL schema as the single DDL source while exposing ORM models for all tables | Codex |
| 2026-10-26 | Python setup | Use the explicit Python 3.11 interpreter when creating `.venv` | The shell default is Python 3.9.6, below the documented minimum | Codex |
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
