"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { z } from "zod";
import { Send, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { MessageSchema, type Message } from "@/lib/messages";
import { ui, type Language } from "@/lib/i18n";
import type { components } from "@/lib/api-types";
const SessionSchema = z.object({ token: z.string(), patient: z.object({ name: z.string(), language: z.enum(["en", "te", "hi"]) }), messages: z.array(MessageSchema) });
const ResultSchema = z.object({ message: MessageSchema, replies: z.array(MessageSchema), alerts: z.array(z.object({ id: z.string(), severity: z.string(), rule_id: z.string(), status: z.string() })), extracted: z.record(z.unknown()) });
const PollSchema = z.object({ items: z.array(MessageSchema), next_after: z.string().nullable() });
export default function PatientSimulator() {
  const { patientId } = useParams<{ patientId: string }>();
  const [session, setSession] = useState<z.infer<typeof SessionSchema> | null>(null);
  const [lang, setLang] = useState<Language>("te");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [english, setEnglish] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<z.infer<typeof ResultSchema> | null>(null);
  const lastOutbound = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const text = ui[lang];
  useEffect(() => {
    let cancelled = false;
    api("/sim/session", SessionSchema, { method: "POST", body: JSON.stringify({ patient_id: patientId }) }).then(value => {
      if (cancelled) return;
      setSession(value); setLang(value.patient.language); setMessages(value.messages);
      const outbound = value.messages.filter(item => item.direction === "out");
      lastOutbound.current = outbound[outbound.length - 1]?.id ?? null;
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : "Session unavailable"));
    return () => { cancelled = true; };
  }, [patientId]);
  useEffect(() => {
    if (!session) return;
    const timer = setInterval(() => {
      const after = lastOutbound.current;
      void api(`/sim/messages?patient_id=${patientId}${after ? `&after=${after}` : ""}`, PollSchema, { headers: { "X-Sim-Token": session.token } }).then(page => {
        if (!page.items.length) return;
        lastOutbound.current = page.items[page.items.length - 1].id;
        setMessages(current => [...current, ...page.items.filter(item => !current.some(existing => existing.id === item.id))]);
      }).catch(() => undefined);
    }, 2000);
    return () => clearInterval(timer);
  }, [session, patientId]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages, busy]);
  async function send(quickReply?: components["schemas"]["SimMessageRequest"]["quick_reply"]) {
    if (!session || busy || (!draft.trim() && !quickReply)) return;
    setBusy(true); setError("");
    const value = quickReply === "not_taken" ? text.missed : quickReply === "yes_taken" ? text.taken : quickReply === "no_symptoms" ? text.okay : draft;
    const payload: components["schemas"]["SimMessageRequest"] = { patient_id: patientId, client_msg_id: crypto.randomUUID(), text: value, language: lang, quick_reply: quickReply ?? null };
    try {
      const [response] = await Promise.all([api("/sim/messages", ResultSchema, { method: "POST", headers: { "X-Sim-Token": session.token }, body: JSON.stringify(payload) }), new Promise(resolve => setTimeout(resolve, 650))]);
      setDraft(""); setResult(response);
      setMessages(current => { const additions = [response.message, ...response.replies]; return [...current, ...additions.filter(item => !current.some(existing => existing.id === item.id))]; });
    } catch (e) { setError(e instanceof Error ? e.message : text.failed); }
    finally { setBusy(false); }
  }
  return <main className="sim-page"><div className="ribbon">SYNTHETIC DATA · PROTOTYPE · NOT FOR CLINICAL USE</div><div className="sim-workspace">
    <section className="phone-frame" aria-label="Patient simulator"><header className="phone-header"><Link href="/sim" aria-label="Choose patient">←</Link><span className="setu-avatar">S</span><div><strong>Setu (demo)</strong><small lang={lang}>{text.title}</small></div><ShieldCheck size={20} /></header>
      <div className="sim-conversation" aria-live="polite" aria-busy={busy}>{messages.map(message => <article key={message.id} className={`sim-bubble ${message.direction === "in" ? "patient-bubble" : "bot-bubble"}`}><p lang={message.language ?? lang}>{message.text}</p>{english && message.text_en && message.text_en !== message.text ? <p className="translation">{message.text_en}</p> : null}<time>{new Date(message.created_at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })}</time></article>)}{busy ? <p className="typing-label" lang={lang}>{text.typing}</p> : null}<div ref={bottom} /></div>
      {error ? <p className="inline-error sim-error" role="alert">{error}</p> : null}
      <div className="quick-replies"><button disabled={busy || !session} onClick={() => void send("yes_taken")} lang={lang}>{text.taken}</button><button disabled={busy || !session} onClick={() => void send("not_taken")} lang={lang}>{text.missed}</button><button disabled={busy || !session} onClick={() => void send("no_symptoms")} lang={lang}>{text.okay}</button></div>
      <form className="sim-composer" onSubmit={e => { e.preventDefault(); void send(); }}><label className="sr-only" htmlFor="chat-message">Message</label><input id="chat-message" lang={lang} maxLength={1000} value={draft} onChange={e => setDraft(e.target.value)} placeholder={text.message} /><button disabled={busy || !session || !draft.trim()} type="submit" aria-label={text.send}><Send size={19} /></button></form>
    </section>
    <aside className="sim-inspector"><Link href="/queue">← Clinician console</Link><h1>Patient check-in</h1><p className="page-intro">{session?.patient.name ?? patientId} · {text.demo}</p><label className="form-stack">{text.language}<select value={lang} onChange={e => setLang(e.target.value as Language)}><option value="te">తెలుగు</option><option value="hi">हिन्दी</option><option value="en">English</option></select></label><label className="checkbox-label"><input type="checkbox" checked={english} onChange={e => setEnglish(e.target.checked)} />{text.english}</label><div className="detail-card"><p className="eyebrow">MOCK AI · OFFLINE</p><h2>{text.understood}</h2>{result ? <><h3>Deterministic rule outcome</h3>{result.alerts.length ? result.alerts.map(alert => <p key={alert.id}><strong>{alert.severity}</strong> · {alert.rule_id} · {alert.status}</p>) : <p>No rule fired.</p>}<details open><summary>Extracted facts</summary><pre>{JSON.stringify(result.extracted, null, 2)}</pre></details></> : <p>{text.pending}</p>}</div><p className="muted">Telugu and Hindi wording is draft content pending native-speaker review.</p></aside>
  </div></main>;
}
