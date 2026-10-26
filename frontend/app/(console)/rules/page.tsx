"use client";
import { useEffect, useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
import { SeveritySchema } from "@/lib/schemas";
import { SeverityBadge } from "@/components/setu/severity-badge";
const Pack = z.object({ name: z.string(), version: z.string(), status: z.string(), rules: z.array(z.object({ id: z.string(), title: z.string(), severity: SeveritySchema, condition: z.string(), sla_minutes: z.number(), rationale: z.string(), clinician_review: z.string() })) });
export default function RulesPage() {
  const [pack, setPack] = useState<z.infer<typeof Pack> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/rules/packs/diabetes_htn", Pack).then(setPack).catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load rules")); }, []);
  return <div className="page-stack"><div><p className="eyebrow">DETERMINISTIC MONITORING</p><h1>Clinical rules</h1><p className="page-intro">Every escalation is backed by a versioned rule.</p></div><div className="review-notice">DRAFT · Thresholds are placeholders pending clinician sign-off.</div>{error ? <p role="alert">{error} · Seed demo data from the demo panel first.</p> : null}{pack ? <><p>{pack.name} · v{pack.version} · {pack.status}</p>{pack.rules.map(rule => <article className="detail-card" key={rule.id}><div className="section-heading"><SeverityBadge severity={rule.severity} /><h2>{rule.title}</h2></div><p><strong>{rule.id}</strong> · SLA {rule.sla_minutes} minutes · clinician review {rule.clinician_review}</p><p className="muted">{rule.condition}</p><p>{rule.rationale}</p></article>)}</> : !error ? <div className="skeleton-row" /> : null}</div>;
}
