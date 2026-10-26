-- Setu prototype schema. SQLite-first.
-- JSON is stored as TEXT; booleans as INTEGER (0/1); timestamps as ISO-8601 UTC TEXT.
-- For Postgres: replace "INTEGER PRIMARY KEY AUTOINCREMENT" with "BIGSERIAL PRIMARY KEY",
-- replace "INSERT OR IGNORE" with "INSERT ... ON CONFLICT DO NOTHING", and optionally use JSONB.
-- (If you use SQLAlchemy models with create_all, you can skip this file and let the models drive the DDL.)
-- Synthetic data only.

CREATE TABLE IF NOT EXISTS clinicians (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  role          TEXT NOT NULL CHECK (role IN ('clinician','admin','health_worker')),
  clinic        TEXT NOT NULL DEFAULT 'Demo Clinic',
  password_hash TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
  id             TEXT PRIMARY KEY,                -- P001
  name           TEXT NOT NULL,
  age            INTEGER NOT NULL,
  sex            TEXT NOT NULL CHECK (sex IN ('M','F','O')),
  language       TEXT NOT NULL CHECK (language IN ('te','hi','en')),
  phone          TEXT,                            -- fake numbers only
  location       TEXT,
  conditions     TEXT NOT NULL DEFAULT '[]',      -- JSON array: ["diabetes","hypertension"]
  discharge_date TEXT NOT NULL,                   -- YYYY-MM-DD
  status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending','active','completed','withdrawn')),
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consents (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id   TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  type         TEXT NOT NULL,                     -- care_messaging
  channel      TEXT NOT NULL,                     -- whatsapp | simulator | voice
  text_version TEXT NOT NULL,
  granted      INTEGER NOT NULL,
  granted_at   TEXT NOT NULL,
  revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id          TEXT PRIMARY KEY,                   -- DOC-0001
  patient_id  TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL,                      -- discharge_summary
  raw_text    TEXT NOT NULL,
  uploaded_by TEXT REFERENCES clinicians(id),
  uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS care_plans (
  id                 TEXT PRIMARY KEY,            -- CP-0001
  patient_id         TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  version            INTEGER NOT NULL,
  status             TEXT NOT NULL CHECK (status IN ('draft','approved','active','completed')),
  plan_json          TEXT NOT NULL,
  warnings_json      TEXT NOT NULL DEFAULT '[]',
  source_document_id TEXT REFERENCES documents(id),
  created_by         TEXT,
  approved_by        TEXT REFERENCES clinicians(id),
  approved_at        TEXT,
  activated_at       TEXT,
  created_at         TEXT NOT NULL,
  UNIQUE (patient_id, version)
);

CREATE TABLE IF NOT EXISTS messages (
  id            TEXT PRIMARY KEY,                 -- M-xxxxxxxx
  patient_id    TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  direction     TEXT NOT NULL CHECK (direction IN ('in','out')),
  channel       TEXT NOT NULL,                    -- simulator | whatsapp
  language      TEXT,
  text          TEXT,
  text_en       TEXT,
  audio_url     TEXT,
  template_key  TEXT,
  intent_json   TEXT,
  client_msg_id TEXT,
  created_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_client ON messages(patient_id, client_msg_id) WHERE client_msg_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_messages_patient_time ON messages(patient_id, created_at);

CREATE TABLE IF NOT EXISTS check_ins (
  id            TEXT PRIMARY KEY,                 -- CI-xxxxxxxx
  patient_id    TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN ('morning','evening')),
  scheduled_for TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','answered','missed')),
  sent_at       TEXT,
  answered_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_checkin_slot ON check_ins(patient_id, kind, scheduled_for);

CREATE TABLE IF NOT EXISTS medication_events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id        TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  care_plan_id      TEXT NOT NULL REFERENCES care_plans(id),
  med_id            TEXT NOT NULL,
  event_date        TEXT NOT NULL,                -- YYYY-MM-DD (IST)
  slot              TEXT NOT NULL CHECK (slot IN ('morning','noon','evening','bedtime')),
  status            TEXT NOT NULL CHECK (status IN ('taken','missed','unsure','unknown')),
  source_message_id TEXT REFERENCES messages(id),
  recorded_at       TEXT NOT NULL,
  UNIQUE (patient_id, med_id, event_date, slot)
);

CREATE TABLE IF NOT EXISTS observations (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id        TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  type              TEXT NOT NULL CHECK (type IN ('glucose','bp','weight')),
  value_num         REAL NOT NULL,                -- glucose mg/dL | systolic | kg
  value_num2        REAL,                         -- diastolic
  unit              TEXT NOT NULL,
  context           TEXT,                         -- fasting | random | morning | unknown
  recorded_at       TEXT NOT NULL,
  source_message_id TEXT REFERENCES messages(id)
);
CREATE INDEX IF NOT EXISTS ix_obs_patient_type_time ON observations(patient_id, type, recorded_at);

CREATE TABLE IF NOT EXISTS symptoms_reported (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id        TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  code              TEXT NOT NULL,
  raw_text          TEXT,
  severity_hint     TEXT CHECK (severity_hint IN ('mild','moderate','severe','unknown')),
  negated           INTEGER NOT NULL DEFAULT 0,
  recorded_at       TEXT NOT NULL,
  source_message_id TEXT REFERENCES messages(id)
);
CREATE INDEX IF NOT EXISTS ix_sym_patient_time ON symptoms_reported(patient_id, recorded_at);

CREATE TABLE IF NOT EXISTS alerts (
  id                TEXT PRIMARY KEY,             -- A-0001
  patient_id        TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  severity          TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  status            TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','snoozed','resolved')),
  rule_id           TEXT NOT NULL,
  rule_version      TEXT NOT NULL,
  title             TEXT NOT NULL,
  summary           TEXT NOT NULL,
  facts_json        TEXT NOT NULL DEFAULT '{}',
  contributing_json TEXT NOT NULL DEFAULT '[]',   -- other fired rules merged in: [{rule_id, rule_version, title, severity}]
  evidence_json     TEXT NOT NULL DEFAULT '[]',   -- [{message_id, at, text, text_en, language}]
  suggested_action  TEXT,
  related_alert_id  TEXT REFERENCES alerts(id),
  assignee          TEXT,
  due_by            TEXT NOT NULL,
  snoozed_until     TEXT,
  acknowledged_by   TEXT REFERENCES clinicians(id),
  acknowledged_at   TEXT,
  resolved_at       TEXT,
  resolution_note   TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_alerts_status_sev ON alerts(status, severity, due_by);
CREATE INDEX IF NOT EXISTS ix_alerts_patient ON alerts(patient_id, rule_id, status);

CREATE TABLE IF NOT EXISTS alert_events (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id  TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
  actor     TEXT NOT NULL,                        -- system | clinician id
  action    TEXT NOT NULL,                        -- created | updated | acknowledged | snoozed | resolved | call_approved | merged
  note      TEXT,
  at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_packs (
  id          TEXT PRIMARY KEY,                   -- diabetes_htn
  name        TEXT NOT NULL,
  version     TEXT NOT NULL,
  status      TEXT NOT NULL,                      -- DRAFT | APPROVED
  yaml_text   TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT,
  loaded_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_evaluations (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id         TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  rule_pack_id       TEXT NOT NULL,
  rule_id            TEXT,                        -- NULL when nothing fired
  rule_version       TEXT,
  fired              INTEGER NOT NULL,
  facts_json         TEXT NOT NULL,
  trigger_message_id TEXT REFERENCES messages(id),
  evaluated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eval_patient_time ON rule_evaluations(patient_id, evaluated_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  actor       TEXT NOT NULL,
  action      TEXT NOT NULL,
  entity      TEXT NOT NULL,
  entity_id   TEXT,
  detail_json TEXT NOT NULL DEFAULT '{}',
  at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log(entity, entity_id, at);

CREATE TABLE IF NOT EXISTS demo_clock (
  id             INTEGER PRIMARY KEY CHECK (id = 1),
  offset_seconds INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO demo_clock (id, offset_seconds) VALUES (1, 0);
