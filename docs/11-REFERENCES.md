# 11 · References

This list is split into what was **checked while preparing this pack** and what is **general starting points to evaluate yourself**. Verify versions and licences before relying on anything.

## Checked during preparation

| Topic | Source | What it confirmed |
|---|---|---|
| Telugu speech-to-text / text-to-speech | Sarvam AI model docs: https://docs.sarvam.ai/api-reference-docs/getting-started/models | Saaras (STT) and Bulbul (TTS) model families list Telugu (te-IN); `mode="transcribe"` for Saaras. Endpoint details are on Sarvam's model and SDK pages |
| WhatsApp integration | Meta WhatsApp Cloud API getting started: https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started | Test phone number via App Dashboard, webhook setup, permanent token via system user, 24-hour customer-service window for non-template messages |
| FHIR in Python | `fhir.resources` on PyPI: https://pypi.org/project/fhir.resources/ | Pydantic-based FHIR model classes (check the version that matches FHIR R4) |
| Metabolic NCD burden in India | ICMR-INDIAB, Lancet Diabetes & Endocrinology 2023: https://doi.org/10.1016/S2213-8587(23)00119-5 | Prevalence figures used in the PRD and deck |
| Adherence | WHO, *Adherence to Long-Term Therapies* (2003): https://www.who.int/news/item/01-07-2003-failure-to-take-prescribed-medicine-for-chronic-diseases-is-a-massive-world-wide-problem | ~50% average adherence in developed countries |

## Build references (well-known tools; check current docs)

- FastAPI: https://fastapi.tiangolo.com
- Pydantic v2: https://docs.pydantic.dev
- SQLAlchemy 2: https://docs.sqlalchemy.org
- APScheduler: https://apscheduler.readthedocs.io
- sse-starlette: https://github.com/sysid/sse-starlette
- Next.js (App Router): https://nextjs.org/docs
- Tailwind CSS: https://tailwindcss.com/docs
- shadcn/ui: https://ui.shadcn.com
- TanStack Query: https://tanstack.com/query
- Recharts: https://recharts.org
- openapi-typescript: https://openapi-ts.dev
- MSW (Mock Service Worker): https://mswjs.io
- Playwright: https://playwright.dev
- Gemini API (pick the current model id yourself): https://ai.google.dev/gemini-api/docs
- HL7 FHIR R4: https://hl7.org/fhir/R4/
- ABDM (Ayushman Bharat Digital Mission): https://abdm.gov.in
- UN Sustainable Development Goals: https://sdgs.un.org/goals
- India Digital Personal Data Protection Act, 2023 (MeitY): https://www.meity.gov.in
- Indian Food Composition Tables 2017 (ICMR-NIN): search "IFCT 2017 NIN Hyderabad"

## How to find good GitHub references (do this in the first hour)

I did not verify specific repositories, so search and judge them yourself. Look for **recent commits, a permissive licence (MIT/Apache-2.0), tests, and clear README**.

Search queries to try on GitHub:
- `fastapi nextjs template` · `fastapi sse example` · `fastapi apscheduler`
- `whatsapp cloud api python` · `whatsapp chatbot fastapi`
- `fhir python pydantic` · `fhir patient bundle example`
- `clinical decision support rule engine yaml` · `json rules engine python`
- `shadcn dashboard template` · `nextjs admin dashboard shadcn`
- `indic nlp telugu` · `ai4bharat` (Indian-language AI models and datasets)
- `healthcare chatbot triage` (study the safety patterns; do not copy medical content)

Rules for reuse: keep the licence file, record the source in `docs/ASSUMPTIONS.md`, never paste code you don't understand, and never import medical content (thresholds, advice) without clinician review.

## Figma references

- Search Figma Community for: *clinical dashboard*, *patient monitoring*, *triage queue*, *WhatsApp chat UI*, *healthcare design system*.
- Use them for **layout inspiration only**; check each file's licence. This pack does not depend on any specific Figma file: tokens and wireframes are in `docs/06` and `frontend/styles/tokens.css`.

## Hackathon submission references

- Look at winning project READMEs on Devpost and GitHub (search "hackathon winner healthcare AI"): note how they present problem, demo GIF, architecture diagram, safety section, and "what's next". Your repo README should have all five.
