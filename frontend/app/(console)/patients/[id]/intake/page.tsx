"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { z } from "zod";
import { api } from "@/lib/api";
import { PlanSchema, type CarePlan } from "@/lib/plans";
export default function IntakePage() {
  const { id } = useParams<{ id: string }>();
  const [source, setSource] = useState("");
  const [plan, setPlan] = useState<CarePlan | null>(null);
  const [edited, setEdited] = useState("");
  const [medsReviewed, setMedsReviewed] = useState(false);
  const [flagsReviewed, setFlagsReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(action: () => Promise<void>) { setBusy(true); setError(""); try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); } finally { setBusy(false); } }
  async function draft() {
    const doc = await api(`/patients/${id}/documents`, z.object({ id: z.string() }), { method: "POST", body: JSON.stringify({ text: source, kind: "discharge_summary" }) });
    const result = await api(`/patients/${id}/care-plans/draft`, PlanSchema, { method: "POST", body: JSON.stringify({ document_id: doc.id }) });
    setPlan(result); setEdited(JSON.stringify(result.plan, null, 2)); setMedsReviewed(false); setFlagsReviewed(false);
  }
  async function save() {
    if (!plan) return;
    const parsed: unknown = JSON.parse(edited);
    const result = await api(`/care-plans/${plan.id}`, PlanSchema, { method: "PATCH", body: JSON.stringify({ plan: z.record(z.unknown()).parse(parsed), expected_version: plan.version }) });
    setPlan(result); setEdited(JSON.stringify(result.plan, null, 2)); setMedsReviewed(false); setFlagsReviewed(false);
  }
  async function transition(action: string) { if (plan) setPlan(await api(`/care-plans/${plan.id}/${action}`, PlanSchema, { method: "POST", body: JSON.stringify({ note: "Reviewed source and structured plan" }) })); }
  return <div className="page-stack"><div><p className="eyebrow">CLINICIAN APPROVAL REQUIRED · {id}</p><h1>Discharge to care plan</h1><p className="page-intro">Review every extracted item against the source before activating check-ins.</p></div>
    {error ? <div className="error-state" role="alert">{error}</div> : null}
    {!plan ? <section className="detail-card form-stack"><div className="page-heading-row"><h2>1. Paste a synthetic discharge summary</h2><button className="secondary-button" disabled={busy} onClick={() => void run(async () => setSource((await api("/demo/sample-summary", z.object({ text: z.string() }))).text))}>Load sample</button></div><label>Discharge summary<textarea className="source-editor" rows={18} value={source} onChange={e => setSource(e.target.value)} /></label><button className="primary-button" disabled={busy || !source.trim()} onClick={() => void run(draft)}>{busy ? "Drafting…" : "Draft plan"}</button></section> : <>
      <div className="review-notice">AI-extracted · needs clinician review. Dose wording is copied from the source. Version {plan.version} · {plan.status.toUpperCase()}</div>
      {plan.warnings.length ? <div className="review-notice">{plan.warnings.map((warning, i) => <p key={i}>{warning}</p>)}</div> : null}
      <section className="intake-grid"><div className="detail-card"><h2>Source document</h2><pre className="source-document">{plan.source_text}</pre></div><div className="detail-card"><h2>2. Review structured plan</h2><p className="muted">Source spans and confidence appear with each item. Edit, remove, or correct items in the editor. Saving creates a new draft version.</p><textarea className="plan-json-editor" aria-label="Editable care plan JSON with source spans" rows={28} value={edited} disabled={busy || plan.status === "active"} onChange={e => setEdited(e.target.value)} /><button className="secondary-button" disabled={busy || plan.status === "active" || edited === JSON.stringify(plan.plan, null, 2)} onClick={() => void run(save)}>Save as new version</button></div></section>
      <section className="detail-card form-stack"><h2>3. Approve and activate</h2><label className="checkbox-label"><input type="checkbox" checked={medsReviewed} onChange={e => setMedsReviewed(e.target.checked)} />I reviewed medicines, verbatim doses, and source evidence.</label><label className="checkbox-label"><input type="checkbox" checked={flagsReviewed} onChange={e => setFlagsReviewed(e.target.checked)} />I reviewed monitoring, red flags, and follow-ups.</label><div className="button-row"><button className="primary-button" disabled={busy || !medsReviewed || !flagsReviewed || plan.status !== "draft" || edited !== JSON.stringify(plan.plan, null, 2)} onClick={() => void run(() => transition("approve"))}>Approve plan</button><button className="primary-button" title="A clinician must approve this version first" disabled={busy || plan.status !== "approved"} onClick={() => void run(() => transition("activate"))}>Activate check-ins</button></div>{plan.status === "active" ? <p role="status">Care plan active. Check-ins start tomorrow at 08:00 IST.</p> : null}</section>
    </>}
  </div>;
}
