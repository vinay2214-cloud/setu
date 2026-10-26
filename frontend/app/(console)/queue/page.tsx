"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, Clock3, Search } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
import { AlertSchema, MetricsSchema, PageSchema, type Alert, type Severity } from "@/lib/schemas";
import { useAlertStream } from "@/lib/sse";
import { AlertDrawer } from "@/components/setu/alert-drawer";
import { SeverityBadge } from "@/components/setu/severity-badge";

const severities: Array<"ALL" | Severity> = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];
const severityRank: Record<Severity, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
const EmptyMetricsSchema = MetricsSchema;

function dueLabel(iso: string, clock: string | null): string {
  const minutes = Math.round((new Date(iso).getTime() - (clock ? Date.parse(clock) : Date.now())) / 60_000);
  if (minutes < 0) return `Overdue ${Math.abs(minutes)}m`;
  if (minutes < 60) return `Due in ${minutes}m`;
  return `Due in ${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export default function QueuePage() {
  const queryClient = useQueryClient();
  const [clock, setClock] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [metrics, setMetrics] = useState<z.infer<typeof MetricsSchema> | null>(null);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [severity, setSeverity] = useState<(typeof severities)[number]>("ALL");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const onAlert = useCallback((updated: Alert) => {
    setAlerts((current) => {
      const exists = current.some((alert) => alert.id === updated.id);
      if (!["open", "acknowledged"].includes(updated.status)) return current.filter((alert) => alert.id !== updated.id);
      return [...(exists ? current.filter((alert) => alert.id !== updated.id) : current), updated]
        .sort((a, b) => severityRank[b.severity] - severityRank[a.severity] || a.due_by.localeCompare(b.due_by));
    });
    setSelected((current) => current?.id === updated.id ? updated : current);
    setToast(`Alert update · ${updated.severity} · ${updated.rule.id}`);
  }, []);
  const connected = useAlertStream(onAlert);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [page, kpis] = await Promise.all([
        queryClient.fetchQuery({ queryKey: ["alerts"], queryFn: () => api("/alerts", PageSchema(AlertSchema)), staleTime: 0 }),
        api("/alerts/metrics", EmptyMetricsSchema),
      ]);
      setAlerts(page.items);
      setMetrics(kpis);
      const state = await api("/demo/state", z.object({ now: z.string() })).catch(() => null);
      if (state) setClock(state.now);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load the priority queue.");
    } finally { setLoading(false); }
  }, [queryClient]);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 15000); return () => clearInterval(timer); }, [refresh]);

  const visible = useMemo(() => alerts.filter((alert) =>
    (severity === "ALL" || alert.severity === severity) &&
    `${alert.patient.name} ${alert.patient.id} ${alert.title} ${alert.rule.id}`.toLowerCase().includes(search.toLowerCase())
  ), [alerts, search, severity]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (selected) return;
      if (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((value) => Math.min(value + 1, visible.length - 1)); }
      if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((value) => Math.max(value - 1, 0)); }
      if (event.key === "Enter" && visible[activeIndex]) { setSelected(visible[activeIndex]); }
      if (event.key.toLowerCase() === "r" && visible[activeIndex]) { setSelected(visible[activeIndex]); }
      if (event.key.toLowerCase() === "a" && visible[activeIndex]) {
        void api(`/alerts/${visible[activeIndex].id}/acknowledge`, AlertSchema, { method: "POST", body: JSON.stringify({ note: "Acknowledged from priority queue" }) }).then(onAlert).catch((cause: unknown) => setToast(cause instanceof Error ? cause.message : "Action failed"));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeIndex, onAlert, visible, selected]);

  const overdue = metrics?.overdue ?? alerts.filter((alert) => Date.parse(alert.due_by) < (clock ? Date.parse(clock) : Date.now())).length;
  return (
    <div className="page-stack">
      <div className="page-heading-row"><div><p className="eyebrow">CLINICIAN WORKLIST</p><h1>Today’s priority queue</h1><p className="page-intro">Review follow-ups in order of severity and urgency.</p></div>
        <span className={`connection-pill ${connected ? "connected" : ""}`}><span className="live-dot" />{connected ? "Live updates" : "Reconnecting…"}</span>
      </div>
      <section className="kpi-grid" aria-label="Queue metrics">
        <Kpi label="Open alerts" value={metrics?.open ?? alerts.length} hint="Needs care team review" />
        <Kpi label="Critical" value={metrics?.by_severity.CRITICAL ?? countSeverity(alerts, "CRITICAL")} hint="Highest priority" />
        <Kpi label="Overdue" value={overdue} hint="Past suggested action time" />
        <Kpi label="Median ack" value={metrics?.median_minutes_to_ack_7d == null ? "—" : `${metrics.median_minutes_to_ack_7d}m`} hint="Acknowledgement · 7 days" />
      </section>
      <div className="queue-toolbar"><div className="filter-group" aria-label="Filter alerts by severity" role="group">
        {severities.map((item) => <button key={item} type="button" className={`filter-chip ${severity === item ? "selected" : ""}`} aria-pressed={severity === item} onClick={() => { setSeverity(item); setActiveIndex(0); }}>{item === "ALL" ? "All" : item[0] + item.slice(1).toLowerCase()}</button>)}
      </div><label className="search-field"><Search size={17} aria-hidden="true" /><span className="sr-only">Search alerts</span><input value={search} onChange={(event) => { setSearch(event.target.value); setActiveIndex(0); }} placeholder="Search patient or rule" /></label></div>
      {toast ? <div className="toast-message" role="status" aria-live="polite">{toast}<button type="button" onClick={() => setToast("")} aria-label="Dismiss notification">×</button></div> : null}
      {error ? <div className="error-state" role="alert"><div><strong>Queue unavailable</strong><p>{error}</p></div><button className="secondary-button" type="button" onClick={() => void refresh()}>Retry</button></div> : null}
      {loading ? <div className="alert-list" aria-label="Loading queue"><div className="skeleton-row" /><div className="skeleton-row" /><div className="skeleton-row" /></div> : visible.length ? (
        <section className="alert-list" aria-label="Alerts" aria-live="polite">
          {visible.map((alert, index) => <button type="button" key={alert.id} onClick={() => { setActiveIndex(index); setSelected(alert); }} className={`alert-card ${index === activeIndex ? "keyboard-active" : ""}`} aria-label={`${alert.severity} alert for ${alert.patient.name}: ${alert.title}`}>
            <span className={`alert-severity-edge edge-${alert.severity.toLowerCase()}`} />
            <div className="alert-card-main"><div className="alert-card-top"><SeverityBadge severity={alert.severity} /><span className="rule-chip">{alert.rule.id} · v{alert.rule.version}</span></div>
              <h2>{alert.title}</h2><p className="alert-patient-line">{alert.patient.name} · {alert.patient.age}{alert.patient.sex} · Day {alert.patient.day_since_discharge} · {alert.patient.language.toUpperCase()}</p>
              <p className="alert-summary">{alert.summary}</p>
            </div><div className="alert-card-meta"><span className={Date.parse(alert.due_by) < (clock ? Date.parse(clock) : Date.now()) ? "overdue-label" : "due-label"}><Clock3 size={15} />{dueLabel(alert.due_by, clock)}</span><span className="status-label">{alert.status}</span><span className="open-hint">Open details <ArrowDown size={14} /></span></div>
          </button>)}
        </section>
      ) : !error ? <div className="empty-state"><CheckCircle2 size={32} /><h2>No open alerts. Everyone is on track.</h2><p>New care team follow-ups will appear here.</p></div> : null}
      <p className="keyboard-hint"><ArrowUp size={14} /><ArrowDown size={14} /> move · Enter open · A acknowledge</p>
      <AlertDrawer alert={selected} onClose={() => setSelected(null)} onUpdated={onAlert} />
    </div>
  );
}

function countSeverity(alerts: Alert[], severity: Severity) { return alerts.filter((alert) => alert.severity === severity).length; }
function Kpi({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return <div className="kpi-tile"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>;
}
