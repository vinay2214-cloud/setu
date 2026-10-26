"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
const StateSchema = z.object({ now:z.string(), llm_provider:z.string(), speech_provider:z.string(), channel:z.string() });
export default function DemoPage() {
  const [state,setState]=useState<z.infer<typeof StateSchema>|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [step,setStep]=useState(1);
  const refresh=useCallback(async()=>setState(await api("/demo/state",StateSchema)),[]);
  useEffect(()=>{void refresh().catch(()=>setMessage("Demo mode is disabled or the API is unavailable."));},[refresh]);
  async function action(path:string,body?:Record<string,unknown>) {
    setBusy(true);setMessage("");
    try { await api(`/demo/${path}`,path==="reset"?z.undefined():z.record(z.unknown()),{method:"POST",body:body?JSON.stringify(body):undefined}); await refresh(); setMessage(`${path} completed.`); }
    catch(e) {setMessage(e instanceof Error?e.message:"Action failed");}
    finally {setBusy(false);}
  }
  return <div className="page-stack"><div><p className="eyebrow">PRESENTATION CONTROLS</p><h1>Demo room</h1><p className="page-intro">Run the synthetic scenario while watching the live clinician queue.</p></div><section className="detail-card"><p className="eyebrow">DEMO CLOCK · ASIA/KOLKATA</p><h2 className="demo-time">{state?`${new Date(state.now).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST`:"Loading…"}</h2><p>AI: <strong>{state?.llm_provider??"—"}</strong> · Channel: {state?.channel??"—"} · Speech: {state?.speech_provider??"none"}</p></section>
    <section className="detail-card form-stack"><h2>Start here</h2><p className="muted">Seed replaces the synthetic scenario. Reset clears patient demo data.</p><div className="button-row"><button className="primary-button" disabled={busy} onClick={()=>{setStep(1);void action("seed",{scenario:"default"});}}>Seed demo data</button><button className="secondary-button" disabled={busy} onClick={()=>void action("reset")}>Reset demo</button><Link className="secondary-button button-link" href="/queue">Open queue</Link><Link className="secondary-button button-link" href="/sim/P001" target="_blank">Open P001 simulator ↗</Link></div></section>
    <section className="detail-card form-stack"><h2>Time and check-ins</h2><div className="button-row"><button className="secondary-button" disabled={busy} onClick={()=>void action("time-travel",{hours:1})}>+1 hour</button><button className="secondary-button" disabled={busy} onClick={()=>void action("time-travel",{days:1})}>+1 day</button><button className="secondary-button" disabled={busy} onClick={()=>void action("check-in",{patient_id:"P001",kind:"morning"})}>Send morning check-in</button></div></section>
    <section className="detail-card form-stack"><h2>Hero scenario</h2><p>1. Morning check-in · 2. Missed medicine · 3. Swollen feet · 4. Approve call · 5. Emergency phrase</p><div className="button-row"><select aria-label="Scenario step" value={step} onChange={e=>setStep(Number(e.target.value))}>{[1,2,3,4,5].map(n=><option key={n} value={n}>Step {n}</option>)}</select><button className="primary-button" disabled={busy} onClick={()=>{void action("scenario-step",{patient_id:"P001",step});setStep(n=>Math.min(5,n+1));}}>Run scenario step</button></div></section>
    <section className="detail-card form-stack"><h2>AI provider for plan drafting</h2><p className="muted">Chat extraction remains deterministic offline. Gemini plan drafting requires server configuration. Patient replies always use templates.</p><div className="button-row"><button className="secondary-button" disabled={busy} onClick={()=>void action("providers",{llm:"mock"})}>Use offline mock</button><button className="secondary-button" disabled={busy} onClick={()=>void action("providers",{llm:"gemini"})}>Use configured Gemini</button></div></section>
    {message?<div className="review-notice" role="status">{message}</div>:null}
  </div>;
}
