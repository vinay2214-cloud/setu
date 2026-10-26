"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AlertSchema, type Alert } from "@/lib/schemas";
import { SeverityBadge } from "./severity-badge";

export function AlertDrawer({ alert, onClose, onUpdated }: {
  alert: Alert | null;
  onClose: () => void;
  onUpdated: (alert: Alert) => void;
}) {
  const panel = useRef<HTMLElement>(null);
  const alertId = alert?.id;
  useEffect(() => {
    if (!alertId) return;
    const previous = document.activeElement as HTMLElement | null;
    const closeButton = panel.current?.querySelector<HTMLButtonElement>("button");
    closeButton?.focus();
    return () => previous?.focus();
  }, [alertId]);
  const [note, setNote] = useState("");
  const [minutes, setMinutes] = useState(120);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!alert) return null;

  async function transition(action: "acknowledge" | "approve-call" | "snooze" | "resolve") {
    if (!alert || (action === "resolve" && !note.trim())) return;
    setBusy(true);
    setError("");
    try {
      const body = action === "approve-call"
        ? { assignee: "dr.anitha", note }
        : action === "snooze" ? { minutes, note } : { note };
      const updated = await api(`/alerts/${alert.id}/${action}`, AlertSchema, {
        method: "POST", body: JSON.stringify(body),
      });
      onUpdated(updated);
      if (action === "resolve") setNote("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The alert could not be updated.");
    } finally { setBusy(false); }
  }

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={panel} className="alert-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
        if (event.key === "Tab") {
          const nodes = panel.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), textarea, select:not(:disabled), input');
          if (!nodes?.length) return;
          const first = nodes[0], last = nodes[nodes.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }}>
        <header className="drawer-header">
          <div><p className="eyebrow">{alert.id} · ALERT REVIEW</p><h2 id="drawer-title">{alert.title}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close alert details" type="button"><X /></button>
        </header>
        <div className="drawer-patient-line"><SeverityBadge severity={alert.severity} /><Link href={`/patients/${alert.patient.id}`}>{alert.patient.name} · {alert.patient.age}{alert.patient.sex} · {alert.patient.language.toUpperCase()} · Day {alert.patient.day_since_discharge}</Link></div>
        <div className="due-banner"><span>Suggested action</span><strong>{alert.suggested_action ?? "Review with care team"}</strong><small>Due {new Date(alert.due_by).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</small></div>
        <section className="drawer-section"><h3>Summary</h3><p>{alert.summary}</p></section>
        <section className="drawer-section"><h3>Evidence</h3>
          {alert.evidence.length ? <ul className="evidence-list">{alert.evidence.map((item) => (
            <li key={item.message_id}><blockquote lang={item.language}>{item.text || "Message text unavailable"}</blockquote>
              {item.text_en ? <p className="translation">“{item.text_en}”</p> : null}
              <time>{new Date(item.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</time>
            </li>
          ))}</ul> : <p className="muted">This seeded alert has no original message evidence.</p>}
        </section>
        <section className="drawer-section"><h3>Why this alert fired</h3>
          <div className="rule-panel"><strong>{alert.rule.id} · v{alert.rule.version}</strong><p>{alert.rule.title}</p><small>Clinician review: {alert.rule.clinician_review}</small></div>
          <div className="flag-list">{alert.contributing_rules.map((rule) => <span key={rule.id} className="rule-flag">{rule.title} · {rule.id}</span>)}</div>
          <details><summary>Facts used</summary><pre>{JSON.stringify(alert.facts_used, null, 2)}</pre></details>
        </section>
        <label className="note-field">Care team note<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} placeholder="Add context for the audit trail" /></label>
        {error ? <p className="inline-error" role="alert">{error}</p> : null}
        <div className="drawer-actions">
          <button className="primary-button" disabled={busy} onClick={() => void transition("approve-call")} type="button">Approve call</button>
          <button className="secondary-button" disabled={busy} onClick={() => void transition("acknowledge")} type="button">Acknowledge</button>
          <div className="snooze-control"><select aria-label="Snooze duration" value={minutes} disabled={busy || alert.severity === "CRITICAL"} onChange={(event) => setMinutes(Number(event.target.value))}>
            <option value={60}>1 hour</option><option value={120}>2 hours</option><option value={240}>4 hours</option>
          </select><button className="secondary-button" disabled={busy || alert.severity === "CRITICAL"} onClick={() => void transition("snooze")} type="button">Snooze</button></div>
          {alert.severity === "CRITICAL" ? <p className="muted full-row">Critical alerts cannot be snoozed.</p> : null}
          <button className="danger-button" disabled={busy || !note.trim()} onClick={() => void transition("resolve")} type="button">Resolve with note</button>
        </div>
        <Link className="patient-record-link" href={`/patients/${alert.patient.id}`}>Open full patient record <ExternalLink size={15} /></Link>
      </section>
    </div>
  );
}
