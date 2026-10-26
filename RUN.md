# Run Setu

Setu is a synthetic-data hackathon prototype. The rules, translated wording, and food ratings remain drafts requiring human review. Use Node.js 22+ and Python 3.11+.

## Local review

```bash
git clone https://github.com/vinay2214-cloud/setu.git
cd setu
scripts/dev.sh
```

On first run the script creates the Python virtual environment, installs locked dependencies, and starts both services. If Python 3.11 is named differently: `PYTHON_BIN=python3 scripts/dev.sh` (it must be 3.11+). Internet is needed to install dependencies once; the mock app then works without keys or external services. Stop both services with Ctrl+C.

Open http://localhost:3000/login and sign in with `dr.anitha@demo.setu` / `demo123`. The admin demo account is `admin@demo.setu` / `demo123`. Startup seeds an empty database once. The **Demo controls** page can reset and seed the scenario again.

Optional configuration: copy `.env.example` to `backend/.env`. Environment variables override that file. Keep `LLM_PROVIDER=mock` for the offline demo. All API calls use the frontend's same-origin proxy; leave `NEXT_PUBLIC_API_BASE` unset. The backend runs on port 8000 and frontend on 3000.

## Hero demo

1. Open **Demo controls**, click **Seed demo data**. Clock starts Day 8, 08:00 IST. Open the priority queue and P001 simulator in separate tabs.
2. Send the morning check-in from Demo controls. In the simulator select Telugu and tap the missed-medicine reply (`లేదు`). The scripted text is `లేదు, ఈ రోజు బాగానే ఉన్నాను.` with quick reply `not_taken`. P001 gets a MEDIUM `R-ADH-01` alert.
3. Send `కాళ్ళు కొంచెం వాచాయి.`. One HIGH `R-COMBO-01` alert appears. Open it: two evidence messages, `R-ADH-01` contributing flag, versioned rule, and suggested action are visible. The earlier MEDIUM alert is merged.
4. Click **Approve call**. The alert is acknowledged and the audit trail records the action. Resolve requires a note; CRITICAL alerts cannot be snoozed.
5. Optional emergency demo: send `ఛాతీలో నొప్పిగా ఉంది`. A CRITICAL `R-CRIT-SYM-01` alert and the fixed Telugu `emergency_advice` reply containing 108 appear.

Alternatively run steps 1–5 directly from Demo controls. Seed again before repeating; scripted steps use idempotent message ids.

To review intake: Patients → P001 → Care plan → Review/create version → Load sample → Draft plan. Inspect source spans and verbatim doses, save edits as a new version, check the review boxes, approve, then activate. Activation before approval returns 409. Unknown discharge summaries in mock mode intentionally produce an empty review draft.

## Verification

```bash
scripts/verify.sh
```

This runs Ruff, backend tests including the complete hero flow and SSE broker delivery, the unchanged 36 golden rule cases, the intent evaluation, OpenAPI generation, TypeScript, ESLint, and a production frontend build. Backend tests use an isolated temporary database.

With the app running, optional real-browser checks:

```bash
cd frontend
npx playwright install chromium
npm test
```

The browser test repeats the hero API scenario three times, checks the live queue/drawer, patient record, plan activation gate, and desktop/mobile layouts. Screenshots are saved to `artifacts/` (ignored by Git).

## Deploy on Render

The repository includes `Dockerfile` and `render.yaml`, following the [Render Blueprint reference](https://render.com/docs/blueprint-spec). The container runs one FastAPI worker and the Next.js standalone server; Next proxies `/api/v1/*` to the backend. This keeps cookies and SSE on one origin.

1. In Render choose **New → Blueprint**, connect `vinay2214-cloud/setu`, select `main`, and review `render.yaml`.
2. The blueprint defines a paid `1c-2g` web service and a 1 GB persistent disk. Review the cost in Render before creating it. SQLite is stored at `/app/data/setu.db`.
3. Render generates `JWT_SECRET`. Keep `APP_ENV=demo`, `DEMO_MODE=true`, `DEMO_AUTO_SEED=true`, and `LLM_PROVIDER=mock`. Do not set `NEXT_PUBLIC_API_BASE`; do not expose API port 8000 separately.
4. Deploy. Health check is `/api/v1/health`. Open the resulting HTTPS URL, log in, and run the same hero demo.

For a free ephemeral preview, create a Docker web service manually, omit the disk, set `DATABASE_URL=sqlite:////app/data/setu.db`, and supply a random JWT secret. Data resets on restart/redeploy. The persistent blueprint is the recommended review setup.

Run the same image locally:

```bash
docker build -t setu-demo .
docker run --rm -p 10000:10000 -e APP_ENV=development -e DEMO_MODE=true -e DEMO_AUTO_SEED=true setu-demo
```

Open http://localhost:10000. Use `APP_ENV=development` for local HTTP; Render's `APP_ENV=demo` uses secure HTTPS cookies. Run one replica/worker because SSE and simulator sessions are held in process.

## Troubleshooting and limits

- Port already used: stop the previous app process or container before starting another copy.
- No patients/rules: sign in and click Seed demo data on `/demo`.
- Simulator session expired after restart: reload that simulator tab.
- A stale plan version returns 409: reload the plan list and edit the latest version.
- Gemini plan drafting is optional. Configure `GEMINI_API_KEY` and `GEMINI_MODEL` on the server, then switch on `/demo`. Its live API needs a key/network and is not part of the offline guarantee. Failures produce an empty review draft; chat extraction stays deterministic.
- Speech/Sarvam, real WhatsApp delivery, FHIR export, and a live PostgreSQL deployment are not implemented/verified. The supplied Render deployment uses SQLite.
- This prototype does not notify a real doctor or call emergency services. “Informed” means an alert was recorded in the demo clinician console. It must only contain synthetic records.
- Telugu/Hindi wording and the DRAFT rule/food packs still require native-speaker, clinician, and dietitian review. `docs/CLINICAL_REVIEW_LOG.md` is reserved for human reviewers.
