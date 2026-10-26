"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { PageSchema, PatientSchema, type Patient } from "@/lib/schemas";
export default function SimulatorPicker() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api("/patients", PageSchema(PatientSchema)).then(page => setPatients(page.items)).catch(() => setError("Sign in to the demo clinician console, then open the simulator.")); }, []);
  return <main className="sim-picker page-stack"><div className="ribbon">SYNTHETIC DATA · PATIENT SIMULATOR</div><h1>Try a patient check-in</h1><p>Choose a synthetic patient. This simulator uses the same rule engine as the clinician console.</p><Link href="/queue">← Clinician console</Link>{error ? <p role="alert">{error} <Link href="/login">Sign in</Link></p> : null}<div className="sim-patient-grid">{patients.map(patient => <Link className="detail-card" key={patient.id} href={`/sim/${patient.id}`}><h2>{patient.name}</h2><p>{patient.id} · {patient.age}{patient.sex} · {patient.language.toUpperCase()}</p><span>Open simulator →</span></Link>)}</div></main>;
}
