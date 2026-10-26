import { z } from "zod";
export const MessageSchema = z.object({ id: z.string(), patient_id: z.string(), direction: z.string(), channel: z.string(), language: z.string().nullable(), text: z.string().nullable(), text_en: z.string().nullable(), template_key: z.string().nullable(), intent: z.record(z.unknown()).nullable(), quick_replies: z.array(z.unknown()), created_at: z.string() });
export type Message = z.infer<typeof MessageSchema>;
