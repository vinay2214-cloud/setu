import { z } from "zod";
export const PlanSchema = z.object({ id: z.string(), patient_id: z.string(), version: z.number(), status: z.string(), plan: z.record(z.string(), z.unknown()), warnings: z.array(z.string()), source_text: z.string(), approved_by: z.string().nullable(), approved_at: z.string().nullable() });
export type CarePlan = z.infer<typeof PlanSchema>;
