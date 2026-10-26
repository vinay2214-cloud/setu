# 06 · Frontend & UX Specification — Setu

Stack: Next.js (App Router) + TypeScript strict + Tailwind + shadcn/ui + lucide-react + TanStack Query + Recharts + zod.
Tokens: `frontend/styles/tokens.css`. API: `04-API-CONTRACT.md` (generate types with `openapi-typescript`). Frontend can be built first against MSW mocks.

## 1. Design principles

1. **Calm, clinical, fast.** The console is a work tool: scannable, low-noise, keyboard friendly.
2. **Evidence over opinion.** Every alert shows why: rule, facts, quoted messages.
3. **Safety is visible.** Approval gates, "AI-extracted – review" badges, and rule provenance are first-class UI, not footnotes.
4. **Never colour alone.** Severity = colour + icon + text label.
5. **Patient UI feels like WhatsApp.** Familiar, large type, big tap targets, local language first.
6. **Honest demo.** A persistent "Synthetic data · Prototype" ribbon; no fake claims.

## 2. Surfaces and routes

| Route | Surface | Purpose | FR |
|---|---|---|---|
| `/login` | Console | Demo login | — |
| `/` → `/queue` | Console | Priority queue + KPI strip | FR-11, 12 |
| `/patients` | Console | Patient list (risk-sorted) | FR-01 |
| `/patients/[id]` | Console | Patient detail (tabs) | FR-20 |
| `/patients/new` | Console | Enrol + consent | FR-01 |
| `/patients/[id]/intake` | Console | Discharge text → AI draft → review/approve | FR-02–04 |
| `/rules` | Console | Rule pack viewer | FR-19 |
| `/demo` | Console (hidden nav) | Demo control panel | FR-22 |
| `/sim` | Simulator | Pick a patient | FR-15 |
| `/sim/[patientId]` | Simulator | Phone-frame chat | FR-15, 16 |

Layout: console uses a left sidebar (Queue, Patients, Rules) + top bar (clinic, demo clock, user). Simulator is centred on a phone frame (max 390 px) with an optional **side panel** (desktop) showing live "what Setu understood" (extracted JSON, rule outcome) for judges.

## 3. Component inventory

**From shadcn/ui:** Button, Badge, Card, Tabs, Table, Sheet (drawer), Dialog, Tooltip, Toast (sonner), Skeleton, Input, Textarea, Select, Switch, Separator, ScrollArea, DropdownMenu, Progress.

**Custom (`components/setu/`):**

| Component | Props (key) | Notes |
|---|---|---|
| `SeverityBadge` | `severity`, `size` | Icon + label: CRITICAL (siren), HIGH (alert-triangle), MEDIUM (alert-circle), LOW (info). Colours from tokens |
| `AlertCard` | `alert`, `onOpen` | Left severity bar, title, patient line, due countdown, rule chip |
| `DueChip` | `dueBy`, `now` | "Due in 3h 12m" / "Overdue 25m" (red); uses demo clock |
| `KpiTile` | `label`, `value`, `hint` | Serif number, small label |
| `EvidenceQuote` | `message` | Original text (language font) + English caption + time + "view in chat" link |
| `RuleChip` | `rule` | `R-COMBO-01 · v1.0.0`, tooltip with rationale; "clinician review required" marker |
| `AdherenceStrip` | `days`, `meds` | Grid of squares per day per medicine: taken ✓ / missed ✕ / unknown · (shapes + colours) |
| `VitalsChart` | `series`, `thresholds` | Recharts line with threshold bands (from rule pack) |
| `ConversationThread` | `messages`, `showTranslation` | Bubble list, language fonts, intent tags on hover |
| `PlanReview` | `plan`, `sourceText` | Two-pane: source text with highlighted spans ↔ structured plan with confidence badges |
| `ConfidenceBadge` | `value` | ≥0.9 "High", 0.75–0.9 "Check", <0.75 "Needs review" (gold) |
| `AIExtractedTag` | — | Gold pill "AI-extracted · review" |
| `PhoneFrame` | children | Rounded device chrome, status bar, header with Setu avatar |
| `ChatBubble` | `dir`, `text`, `lang`, `time` | Uses `:lang()` fonts |
| `QuickReplies` | `options` | Large pill buttons (min height 48px) |
| `VoiceRecorder` | `onAudio` | Press-and-hold mic, waveform, 30 s limit, permission error state |
| `LanguageToggle` | `value` | తెలుగు / हिन्दी / English |
| `DemoClockControl` | — | Shows clock; buttons +1 day, +1 h, "Send check-in", scenario step |
| `EmptyState`, `ErrorState`, `SkeletonRows` | — | Consistent states |
| `SyntheticRibbon` | — | "Synthetic demo data · Prototype · Not for clinical use" |

## 4. Screen specifications

### 4.1 Priority Queue (`/queue`) — the hero screen

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Setu · Demo Clinic            ◷ Day 8 · 09:12 IST      Dr. Anitha ▾      │
├────────┬─────────────────────────────────────────────────────────────────┤
│ Queue  │  Today's priority queue                          [Live ●]      │
│ Patients│ ┌──────┬──────┬───────────┬─────────────┐                      │
│ Rules  │ │Open 4│Crit 0│Overdue 1  │Median ack 22m│   KPI strip          │
│        │ └──────┴──────┴───────────┴─────────────┘                      │
│        │  Filters: [All] [Critical] [High] [Medium] [Low]  Search…       │
│        │ ┃▲ HIGH   Ramesh K., 58M · Day 8     Missed dose ×2 + swelling  │
│        │ ┃        R-COMBO-01 · Call within 4 hours     Due in 3h 41m  ›  │
│        │ ┃● MEDIUM Lakshmi D., 64F · Day 5    Missed dose ×2             │
│        │ ┃        R-ADH-01 · Due in 19h                                ›  │
│        │ ┃ⓘ LOW    Suresh P., 49M · Day 3     Question for doctor        │
│        │  …                                                              │
└────────┴─────────────────────────────────────────────────────────────────┘
```
- Sorted severity desc, then `due_by` asc. New alerts slide in at the right position with a 1.5 s highlight and a toast "New HIGH alert: Ramesh K." (SSE).
- Click row → Alert drawer (§4.3). Keyboard: ↑/↓ move, Enter open, `a` acknowledge, `r` resolve.
- Empty state: "No open alerts. Everyone is on track." with a check icon.

### 4.2 Patient detail (`/patients/[id]`)

Header: avatar, name, age/sex, language chip, conditions chips, "Day 8 post-discharge", plan status chip, adherence 7-day %, open alerts count.
Tabs:
1. **Overview** — AdherenceStrip (14 days), VitalsChart (glucose, BP) with threshold bands, recent symptoms list, next follow-up.
2. **Conversation** — ConversationThread with "Show English" toggle, intent tags, link from alert evidence scrolls to message.
3. **Care plan** — current plan (read-only unless editing), version history, approved by/at, "Edit → new version".
4. **Alerts** — history with outcomes and notes.
5. **Audit** — chronological audit entries (who, what, when).

### 4.3 Alert drawer (Sheet, right, 520 px)

```
┌─ A-0007 ───────────────────────────────────────── ✕ ┐
│ ▲ HIGH   Missed dose ×2 with new leg swelling        │
│ Ramesh Kumar · 58M · Telugu · Day 8                   │
│ Due in 3h 41m  [Call within 4 hours]                  │
│──────────────────────────────────────────────────────│
│ Summary (AI-written from evidence)                    │
│ 58M, day 8 post-discharge. Missed critical medicines  │
│ two days running and reports leg swelling today.      │
│──────────────────────────────────────────────────────│
│ Evidence                                              │
│ ❝ లేదు, ఈ రోజు బాగానే ఉన్నాను.   09:10                 │
│   "No, I'm feeling fine today."                       │
│ ❝ కాళ్ళు కొంచెం వాచాయి.          09:11                 │
│   "My feet are a bit swollen."                        │
│──────────────────────────────────────────────────────│
│ Why this fired                                        │
│ Rule R-COMBO-01 v1.0.0 · clinician review: required   │
│ Flags: [Missed dose ×2 · R-ADH-01] [Leg swelling]     │
│ facts: missed streak = 2 · symptoms = leg_swelling    │
│──────────────────────────────────────────────────────│
│ [Approve call]  [Acknowledge]  [Snooze ▾]  [Resolve]  │
│ Note (required to resolve) ________________________   │
└───────────────────────────────────────────────────────┘
```
- "Approve call" assigns and marks `call_approved`; toast confirms.
- Resolve requires a note; CRITICAL has no snooze.
- Footer link: "Open full patient record".

### 4.4 Intake and plan review (`/patients/[id]/intake`)

Step 1 **Paste summary** (large textarea, "Load sample" button inserts `discharge_summary_ramesh.txt`) → **Draft plan**.
Step 2 **Review** (`PlanReview`): left = source text with coloured highlight per item; right = structured plan cards (medicines, monitoring, diet, red flags, follow-ups). Each item: `AIExtractedTag`, `ConfidenceBadge`, inline edit, criticality toggle (critical/standard), delete. Warnings banner for dropped items.
Step 3 **Approve and activate**: checklist ("I reviewed medicines and doses", "I reviewed red flags") → Approve → Activate. Buttons disabled until previous step is done. Success shows "Check-ins start tomorrow 08:00 IST".

### 4.5 Rules (`/rules`)

Pack header (name, version, **status DRAFT/APPROVED**, approved by/at) and a table: id, title, severity badge, plain-English condition, SLA, rationale. Banner for DRAFT: "Thresholds are placeholders pending clinician sign-off."

### 4.6 Demo panel (`/demo`)

Buttons: Seed demo data · Reset · +1 hour · +1 day · Send morning check-in · Scenario step ▸ (Ramesh) · Provider switch (mock / Gemini) · Speech on/off · Open simulator for P001. Shows current clock and provider state. Large, readable from across a room.

### 4.7 Patient simulator (`/sim/[patientId]`)

```
┌─────────────── Desktop ────────────────────────────────────────────────┐
│  ┌────────── Phone ──────────┐   ┌── What Setu understood ──────────┐ │
│  │ ◀ Setu · Care companion   │   │ Language: te   Confidence 0.93   │ │
│  │ ───────────────────────── │   │ Intent: symptom_report           │ │
│  │ శుభోదయం రమేశ్ గారు! …      │   │ Symptoms: leg_swelling           │ │
│  │      [ అవును, వేసుకున్నాను ]  │   │ Rule fired: R-COMBO-01 (HIGH)    │ │
│  │      [ లేదు ]               │   │ Clinician alerted ✓              │ │
│  │ ───────────────────────── │   └──────────────────────────────────┘ │
│  │ [🎤] [  Type…        ] [➤] │   [తెలుగు|हिन्दी|English] [Show English]│
│  └───────────────────────────┘                                         │
└────────────────────────────────────────────────────────────────────────┘
```
- Mobile (<640 px): phone fills the viewport; side panel hidden.
- Language toggle changes UI strings and the language sent with messages.
- "Show English" toggles translation captions under each bubble.
- Typing indicator for 600–900 ms before bot replies (feels human, hides latency).
- Voice: hold mic → record → upload; while transcribing show "Listening…"; errors show "Please type instead".
- Delivered/read ticks are decorative; do not imply real WhatsApp. Header says "Setu (demo)".

## 5. States and edge cases

| Situation | UI behaviour |
|---|---|
| Loading | Skeleton rows/cards, never spinners alone |
| API error | Inline `ErrorState` with retry; toast for actions |
| SSE disconnected | Small "Reconnecting…" pill; refetch on reconnect |
| Offline mock | Banner "Mock AI active" in demo panel and simulator side panel |
| Long Telugu text | Wrap, no truncation in bubbles; truncate with tooltip in lists |
| Concurrent edit | If plan version changed, show conflict dialog with diff |
| Permission mic denied | Explain and fall back to text |
| Snooze on CRITICAL | Disabled with tooltip |

## 6. Accessibility

WCAG 2.2 AA: contrast ≥ 4.5:1 (token pairs above are chosen for this), visible focus rings (2 px brand-700 + offset), full keyboard operation, `aria-live="polite"` for new alerts and chat messages, `lang` attribute on every message element, touch targets ≥ 44×44 px, respects `prefers-reduced-motion`. Charts have data tables as accessible alternatives.

## 7. Content and microcopy

- Tone: calm, plain, respectful. No jargon in patient UI. Clinician UI uses concise clinical shorthand.
- Always address patient as "{Name} గారు" (te) / "{Name} जी" (hi).
- Never promise outcomes ("You are safe"). Use "I have informed your doctor".
- Buttons: verbs ("Approve call", "Resolve with note").
- Patient-facing strings live in `lib/i18n.ts` (UI chrome) and `seed/message_templates.json` (bot messages).

## 8. Data layer

- `lib/api.ts`: typed fetch wrapper (base URL from `NEXT_PUBLIC_API_BASE`, credentials include, error normaliser).
- Query keys: `['alerts', filters]`, `['patient', id]`, `['patient', id, 'timeline']`, `['messages', id]`.
- `useAlertStream()` opens `EventSource('/alerts/stream')`; on `alert.created|updated` update the query cache; on error backoff 1s→10s.
- Optimistic updates for acknowledge/snooze; roll back on error.
- Simulator keeps messages in local state seeded from `GET /patients/{id}/messages`, appends replies from `POST /sim/messages`, and polls/streams for scheduled check-ins.

## 9. Folder structure

```
frontend/
  app/
    (console)/layout.tsx           # sidebar + topbar + SyntheticRibbon
    (console)/queue/page.tsx
    (console)/patients/page.tsx
    (console)/patients/new/page.tsx
    (console)/patients/[id]/page.tsx
    (console)/patients/[id]/intake/page.tsx
    (console)/rules/page.tsx
    (console)/demo/page.tsx
    sim/page.tsx
    sim/[patientId]/page.tsx
    login/page.tsx
    layout.tsx  globals.css
  components/ui/            # shadcn
  components/setu/          # custom components above
  lib/{api.ts,sse.ts,i18n.ts,format.ts,clock.ts}
  mocks/{handlers.ts,fixtures.ts}   # MSW from API contract + seed
  styles/tokens.css
```

## 10. Using Figma (optional, recommended for polish)

You do not need a Figma file to build; wireframes and tokens above are enough for agents. If you want Figma for the pitch:
1. Create variables from `tokens.css` (colours, radius, spacing) and text styles for Inter / Noto Sans Telugu.
2. Build frames in this order: Queue, Alert drawer, Patient detail, Plan review, Simulator.
3. Export key frames as PNG for the deck. Keep real screenshots from the running app for the final submission, since judges value working software over mock-ups.
4. When searching Figma Community for inspiration use terms such as *"clinical dashboard"*, *"patient monitoring"*, *"triage queue"*, *"chat UI WhatsApp"*, and *"healthcare design system"*. **Check each file's licence before reusing anything**; this pack does not depend on any specific community file.

## 11. Frontend acceptance checklist

- [ ] Queue updates live without refresh; new HIGH alert appears in < 2 s.
- [ ] Every alert shows rule id/version and ≥ 1 quoted evidence message.
- [ ] Plan cannot be activated before approval (button disabled + tooltip).
- [ ] Simulator works fully in te, hi, en; fonts render; Show English toggles.
- [ ] Severity is distinguishable in greyscale.
- [ ] Keyboard-only run through queue → alert → resolve works.
- [ ] No console errors; Lighthouse accessibility ≥ 90 on queue and simulator.
- [ ] Works at 1280×720 (projector) and at 390 px width (simulator).
