# Verification record

Verified on 26 October 2026 with `LLM_PROVIDER=mock`.

The required P0–P6 phases and P8 hardening are implemented. P7 speech, real WhatsApp, and FHIR are skipped. Gemini plan drafting is implemented but has not been called with a live key. SQLite is the verified deployment database. Native-speaker/clinical review and Lighthouse scoring remain human/optional checks; no clinical review was claimed.

## Recorded command output

`scripts/verify.sh` exited 0:

```text
All checks passed!
54 files already formatted
51 passed, 1 warning
```

The warning is FastAPI/Starlette's httpx TestClient deprecation. The unchanged reference rule runner passed all 36 cases. TypeScript, ESLint, and `next build --webpack` completed successfully. Generated routes include login, queue, patients, patient detail/intake, enrolment, rules, simulator, and demo controls.

```text
language | symptom TP | symptom FP | symptom FN | precision | recall | critical recall
en | 6 | 0 | 0 | 100% | 100% | 100%
hi | 5 | 0 | 0 | 100% | 100% | 100%
te | 6 | 0 | 0 | 100% | 100% | 100%
critical symptom recall: 8/8 (100%)
medication status accuracy: 8/8 (100%)
vital extraction exact match: 5/5 (100%)
needs-human safety coverage: 10/10 (100%)
expected negation accuracy: 2/2 (100%)
symptom confusion totals: TP=17, FP=0, FN=0
```

`cd frontend && npm test`, with external browser requests blocked:

```text
Live HIGH alert visible in 37 ms
PASS: login, hero 3x, live queue, drawer action, patient record, intake gate, desktop/mobile simulator, no page errors.
```

The checks include 1280×720 desktop and 390 px mobile viewports, no horizontal overflow on the simulator, source review before plan activation, idempotent POST replay after alert upgrade, merged evidence, and a fixed Telugu emergency template containing 108. Screenshots are written to `artifacts/` and ignored by Git.

Dependency installation/audit reported `found 0 vulnerabilities` after updating Next.js/React/Zod and patching the transitive CSS parser.

`docker build -t setu-demo .` completed successfully with clean Linux dependency installation. The container's same-origin API returned:

```text
{"status":"ok","db":"ok","rules_loaded":22,"llm":"mock"}
Container login HTTP 200
```

Render itself has not been deployed; the user will deploy it after reviewing the application. The Blueprint uses a paid persistent disk and one API worker. See [RUN.md](../RUN.md) for exact commands, demo script, configuration, and limitations.

Phase reviews were performed by a second agent. Reported blockers were corrected. `docs/CLINICAL_REVIEW_LOG.md` was not edited.
