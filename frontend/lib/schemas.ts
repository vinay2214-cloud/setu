import { z } from "zod";

export const SeveritySchema = z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);
export const PatientSchema = z.object({
  id: z.string(),
  name: z.string(),
  age: z.number(),
  sex: z.string(),
  language: z.enum(["te", "hi", "en"]),
  location: z.string().nullable().optional(),
  conditions: z.array(z.string()),
  discharge_date: z.string(),
  day_since_discharge: z.number(),
  status: z.string(),
  plan: z.object({ id: z.string(), status: z.string(), version: z.number() }).nullable(),
  risk: z.object({
    open_alerts: z.number(),
    highest_severity: SeveritySchema.nullable(),
    adherence_7d: z.number().nullable(),
    last_response_at: z.string().nullable(),
  }),
});

export const AlertSchema = z.object({
  id: z.string(),
  patient: z.object({
    id: z.string(), name: z.string(), age: z.number(), sex: z.string(),
    language: z.string(), day_since_discharge: z.number(),
  }),
  severity: SeveritySchema,
  status: z.string(),
  title: z.string(),
  summary: z.string(),
  rule: z.object({ id: z.string(), version: z.string(), title: z.string(), clinician_review: z.string() }),
  facts_used: z.record(z.string(), z.unknown()),
  contributing_rules: z.array(z.object({ id: z.string(), version: z.string(), title: z.string(), severity: SeveritySchema })),
  related_alert_id: z.string().nullable(),
  evidence: z.array(z.object({ message_id: z.string(), at: z.string(), text: z.string().nullable(), text_en: z.string().nullable(), language: z.string() })),
  suggested_action: z.string().nullable(),
  due_by: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  acknowledged_by: z.string().nullable(),
  resolved_at: z.string().nullable(),
  snoozed_until: z.string().nullable(),
  events: z.array(z.object({ at: z.string(), actor: z.string(), action: z.string(), note: z.string().nullable() })),
});

export const PageSchema = <T extends z.ZodTypeAny>(item: T) => z.object({
  items: z.array(item),
  next_cursor: z.string().nullable().optional(),
});

export const MetricsSchema = z.object({
  open: z.number(),
  by_severity: z.record(z.string(), z.number()),
  median_minutes_to_ack_7d: z.number().nullable(),
  overdue: z.number(),
});

export type Patient = z.infer<typeof PatientSchema>;
export type Alert = z.infer<typeof AlertSchema>;
export type Severity = z.infer<typeof SeveritySchema>;
