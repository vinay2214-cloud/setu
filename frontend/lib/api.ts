import type { components } from "./api-types";
import { z } from "zod";

const baseUrl = (process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      const parsed = z.object({ error: z.object({ message: z.string() }) }).safeParse(body);
      if (parsed.success) message = parsed.data.error.message;
    } catch { /* Keep the status-based message for non-JSON errors. */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return schema.parse(undefined);
  const body: unknown = await response.json();
  return schema.parse(body);
}

export const jsonBody = (body: components["schemas"]["LoginRequest"] | Record<string, unknown>): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});

export const apiBaseUrl = baseUrl;
