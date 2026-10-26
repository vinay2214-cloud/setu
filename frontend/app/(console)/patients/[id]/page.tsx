"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, ClipboardCheck, MessageSquareText, ShieldAlert, UserRound } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { AlertSchema, PageSchema, PatientSchema, type Alert, type Patient } from "@/lib/schemas";
import { SeverityBadge } from "@/components/setu/severity-badge";

const MessageSchema = z.object({
  id: z.string(), patient_id: z.string(), direction: z.string(), channel: z.string(), language: z.string(),
  text: z.string().nullable(), text_en: z.string().nullable(), template_key: z.string().nullable(),
  intent: z.record(z.unknown()).nullable(), quick_replies: z.array(z.unknown()), created_at: z.string(),
});
const ObservationSchema = z.object({
  id: z.number().optional(), type: z.string(), value_num: z.number().nullable().optional(),
  value_num2: z.number().nullable().optional(), unit: z.string().nullable().optional(), context: z.string().nullable().optional(), recorded_at: z.string(),
});
const TimelineSchema = z.object({ type: z.string(), at: z.string(), data: z.record(z.unknown()) });
const AdherenceSchema = z.object({ event_date: z.string(), med_id: z.string(), slot: z.string(), status: z.string() });
const TimelinePageSchema = PageSchema(TimelineSchema);
const ObservationPageSchema = PageSchema(ObservationSchema);
const AdherencePageSchema = PageSchema(AdherenceSchema);
const tabs = ["Overview", "Conversation", "Care plan", "Alerts", "Audit"] as const;
type Tab = (typeof tabs)[number];

export default function PatientDetailPage() {
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [messages, setMessages] = useState<z.infer<typeof MessageSchema>[]>([]);
  const [observations, setObservations] = useState<z.infer<typeof ObservationSchema>[]>([]);
  const [timeline, setTimeline] = useState<z.infer<typeof TimelineSchema>[]>([]);
  const [adherence, setAdherence] = useState<z.infer<typeof AdherenceSchema>[]>([]);
  const [tab, setTab] = useState<Tab>("Overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [p, alertPage, messagePage, vitalPage, timelinePage, adherencePage] = await Promise.all([
        api(`/patients/${patientId}`, PatientSchema),
        api(`/alerts?patient_id=${encodeURIComponent(patientId)}&status=open,acknowledged,resolved`, PageSchema(AlertSchema)),
        api(`/patients/${patientId}/messages?limit=100`, PageSchema(MessageSchema)),
        api(`/patients/${patientId}/vitals?type=glucose&days=90&limit=100`, ObservationPageSchema),
        api(`/patients/${patientId}/timeline?limit=100`, TimelinePageSchema),
        api(`/patients/${patientId}/adherence?days=14&limit=100`, AdherencePageSchema),
      ]);
      setPatient(p); setAlerts(alertPage.items); setMessages(messagePage.items); setObservations(vitalPage.items);
      setTimeline(timelinePage.items); setAdherence(adherencePage.items);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load patient record."); }
    finally { setLoading(false); }
  }, [patientId]);
  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="page-stack"><div className="skeleton-row" /><div className="skeleton-row" /><div className="skeleton-row" /></div>;
  if (error || !patient) return <div className="error-state" role="alert"><p>{error || "Patient not found."}</p><button className="secondary-button" onClick={() => void load()} type="button">Retry</button></div>;
  const chartData = observations.filter((item) => item.value_num != null).map((item) => ({
    date: new Date(item.recorded_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" }),
    value: item.value_num as number,
  }));
  const adherenceRate = patient.risk.adherence_7d == null ? null : Math.round(patient.risk.adherence_7d * 100);

  return <div className="page-stack">
    <Link href="/patients" className="back-link">← All patients</Link>
    <section className="patient-profile-card">
      <span className="patient-profile-avatar"><UserRound size={26} /></span>
      <div className="patient-profile-copy"><p className="eyebrow">PATIENT RECORD · {patient.id}</p><h1>{patient.name}</h1>
        <p>{patient.age}{patient.sex} · <span lang={patient.language}>{patient.language.toUpperCase()}</span> · Day {patient.day_since_discharge} post-discharge</p>
        <div className="condition-list">{patient.conditions.map((condition) => <span className="condition-chip" key={condition}>{condition.replaceAll("_", " ")}</span>)}</div>
      </div>
      <div className="patient-profile-stats"><span>Care plan</span><strong>{patient.plan?.status ?? "Not created"}</strong><span>7-day adherence</span><strong>{adherenceRate == null ? "—" : `${adherenceRate}%`}</strong><span>Open alerts</span><strong>{patient.risk.open_alerts}</strong></div>
    </section>
    <nav className="patient-tabs" aria-label="Patient record sections">
      {tabs.map((item) => <button key={item} type="button" aria-pressed={tab === item} className={tab === item ? "tab-active" : ""} onClick={() => setTab(item)}>{item}</button>)}
    </nav>
    {tab === "Overview" ? <section className="patient-panel">
      <div className="detail-grid"><div className="detail-card"><div className="section-heading"><ClipboardCheck size={18} /><h2>Medication adherence</h2></div><p className="muted">Recent recorded events · last 14 days</p>
        {adherence.length ? <div className="adherence-table"><div className="adherence-head"><span>Date</span><span>Medicine</span><span>Slot</span><span>Status</span></div>{adherence.map((event, index) => <div className="adherence-row" key={`${event.event_date}-${event.med_id}-${event.slot}-${index}`}><span>{event.event_date}</span><span>{event.med_id}</span><span>{event.slot}</span><span className={`event-status status-${event.status}`}>{event.status}</span></div>)}</div> : <p className="empty-inline">No medication events recorded in this window.</p>}
      </div><div className="detail-card"><div className="section-heading"><Activity size={18} /><h2>Home glucose readings</h2></div><p className="muted">Recorded observations · mg/dL</p>
        {chartData.length ? <><div className="chart-frame"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><XAxis dataKey="date" /><YAxis width={38} /><Tooltip /><Line type="monotone" dataKey="value" stroke="var(--brand-700)" strokeWidth={2} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div><table className="visually-hidden"><caption>Glucose reading data</caption><thead><tr><th>Date</th><th>Value</th></tr></thead><tbody>{chartData.map((item, index) => <tr key={`${item.date}-${index}`}><td>{item.date}</td><td>{item.value} mg/dL</td></tr>)}</tbody></table></> : <p className="empty-inline">No glucose readings recorded in this window.</p>}
      </div></div>
      <div className="detail-card"><div className="section-heading"><Activity size={18} /><h2>Recent care timeline</h2></div>{timeline.length ? <ol className="timeline-list">{timeline.slice(0, 8).map((item, index) => <li key={`${item.type}-${item.at}-${index}`}><time>{new Date(item.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time><strong>{item.type.replaceAll("_", " ")}</strong><span>{timelineSummary(item)}</span></li>)}</ol> : <p className="empty-inline">No recent timeline events.</p>}</div>
    </section> : null}
    {tab === "Conversation" ? <section className="conversation-panel" aria-label="Patient conversation">{messages.length ? messages.map((message) => <article className={`conversation-message ${message.direction === "out" ? "message-out" : "message-in"}`} key={message.id}>
      <p lang={message.language}>{message.text || "(No text)"}</p>{message.text_en && message.text_en !== message.text ? <p className="translation">{message.text_en}</p> : null}
      <footer><time>{new Date(message.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time><span>{message.direction === "in" ? "Patient" : "Setu · approved template"}</span>{message.template_key ? <span>{message.template_key}</span> : null}</footer>
    </article>) : <div className="empty-state"><MessageSquareText size={28} /><h2>No messages yet</h2></div>}</section> : null}
    {tab === "Care plan" ? <section className="patient-panel"><div className="detail-card"><div className="section-heading"><ClipboardCheck size={18} /><h2>Current care plan</h2><Link href={`/patients/${patientId}/intake`}>Review / create version →</Link></div>{patient.plan ? <><p>Plan <strong>{patient.plan.id}</strong> · version {patient.plan.version}</p><span className={`plan-status status-${patient.plan.status}`}>{patient.plan.status}</span><p className="muted">Care plan contents are reviewed and maintained by the clinical team.</p></> : <p className="empty-inline">No care plan is recorded for this patient.</p>}</div><div className="review-notice">Plan changes require clinician review and approval before activation.</div></section> : null}
    {tab === "Alerts" ? <section className="alert-history-list">{alerts.length ? alerts.map((alert) => <article className="history-alert" key={alert.id}><div><SeverityBadge severity={alert.severity} /><strong>{alert.title}</strong></div><span>{alert.id} · {alert.status} · {alert.rule.id}</span><time>{new Date(alert.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time><p>{alert.evidence.length} evidence messages · {alert.events.length} recorded actions</p></article>) : <div className="empty-state"><ShieldAlert size={28} /><h2>No alerts recorded</h2></div>}</section> : null}
    {tab === "Audit" ? <section className="patient-panel"><div className="detail-card"><div className="section-heading"><ShieldAlert size={18} /><h2>Alert audit trail</h2></div>{alerts.flatMap((alert) => alert.events.map((event, index) => ({ ...event, alertId: alert.id, index }))).length ? <ol className="timeline-list">{alerts.flatMap((alert) => alert.events.map((event, index) => ({ ...event, alertId: alert.id, index }))).sort((a, b) => b.at.localeCompare(a.at)).map((event) => <li key={`${event.alertId}-${event.index}`}><time>{new Date(event.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time><strong>{event.action} · {event.alertId}</strong><span>{event.actor}{event.note ? ` · ${event.note}` : ""}</span></li>)}</ol> : <p className="empty-inline">No alert audit events are available.</p>}<p className="muted">This view lists alert actions returned by the audit-backed alert API.</p></div></section> : null}
  </div>;
}

function timelineSummary(item: z.infer<typeof TimelineSchema>): string {
  const data = item.data;
  if (item.type === "alert") return `${String(data.severity ?? "")} · ${String(data.title ?? "")}`;
  if (item.type === "symptom") return String(data.code ?? "Reported symptom");
  if (item.type === "observation") return `${String(data.type ?? "Reading")}: ${String(data.value_num ?? "")}${data.value_num2 ? `/${String(data.value_num2)}` : ""} ${String(data.unit ?? "")}`;
  if (item.type === "medication") return `${String(data.med_id ?? "Medicine")} · ${String(data.status ?? "")}`;
  return String(data.kind ?? item.type.replaceAll("_", " "));
}
