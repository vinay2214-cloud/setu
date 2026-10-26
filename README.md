# Setu · the care between visits

Post-discharge continuity for type 2 diabetes and hypertension in India. A clinician reviews a source-backed care plan; patients check in in Telugu, Hindi, or English; deterministic rules surface follow-up needs with evidence.

**Synthetic data · Hackathon prototype · Not for clinical use.**

```bash
scripts/dev.sh
```

Open http://localhost:3000/login. Demo login: `dr.anitha@demo.setu` / `demo123`.

- Clinician queue, alert actions, audit history, patient records and charts
- Source-verified plan drafts, versioning, clinician approval and activation gate
- Multilingual patient simulator, fixed emergency templates, offline mock provider
- Daily check-ins, demo clock and scenario controls, template-based food tips
- Docker + Render Blueprint with a persistent SQLite disk

[Setup, demo, verification, and Render deployment](RUN.md) · [Product requirements](docs/01-PRD.md) · [Safety rules](AGENTS.md)

```bash
scripts/verify.sh
```

“Automate the gaps, never the doctor.”
