"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Search, UserRound, Users } from "lucide-react";
import { api } from "@/lib/api";
import { PageSchema, PatientSchema, type Patient } from "@/lib/schemas";
import { SeverityBadge } from "@/components/setu/severity-badge";

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async (filter: string) => {
    setLoading(true);
    try {
      const page = await api(`/patients?limit=100${filter ? `&q=${encodeURIComponent(filter)}` : ""}`, PageSchema(PatientSchema));
      setPatients(page.items);
      setError("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load patients."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(query); }, [load, query]);
  return (
    <div className="page-stack">
      <div className="page-heading-row"><div><p className="eyebrow">CARE ROSTER</p><h1>Patients</h1><p className="page-intro">Synthetic patients ordered by current follow-up risk.</p></div><Link href="/patients/new" className="primary-button button-link">Enrol demo patient</Link><span className="count-chip"><Users size={16} />{patients.length} patients</span></div>
      <form className="patient-search-row" onSubmit={(event) => { event.preventDefault(); setQuery(search.trim()); }}>
        <label className="search-field"><Search size={17} /><span className="sr-only">Search patients</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name or patient ID" /></label>
        <button className="secondary-button" type="submit">Search</button>
      </form>
      {error ? <div className="error-state" role="alert"><p>{error}</p><button className="secondary-button" onClick={() => void load(query)} type="button">Retry</button></div> : null}
      {loading ? <div className="patient-table skeleton-table"><div /><div /><div /></div> : patients.length ? <div className="patient-table" role="list" aria-label="Patient roster">
        <div className="patient-table-head" aria-hidden="true"><span>Patient</span><span>Conditions</span><span>Care plan</span><span>Adherence · 7 days</span><span>Open alerts</span></div>
        {patients.map((patient) => <Link className="patient-table-row" role="listitem" href={`/patients/${patient.id}`} key={patient.id}>
          <span className="patient-cell"><span className="patient-avatar"><UserRound size={18} /></span><span><strong>{patient.name}</strong><small>{patient.id} · {patient.age}{patient.sex} · Day {patient.day_since_discharge}</small></span></span>
          <span className="condition-list">{patient.conditions.map((condition) => <span className="condition-chip" key={condition}>{condition.replaceAll("_", " ")}</span>)}</span>
          <span><span className={`plan-status status-${patient.plan?.status ?? "missing"}`}>{patient.plan?.status ?? "No plan"}</span></span>
          <span>{patient.risk.adherence_7d == null ? "—" : `${Math.round(patient.risk.adherence_7d * 100)}%`}</span>
          <span className="open-alerts-cell">{patient.risk.highest_severity ? <SeverityBadge severity={patient.risk.highest_severity} /> : <span className="muted">None</span>}<small>{patient.risk.open_alerts} open</small></span>
        </Link>)}
      </div> : !error ? <div className="empty-state"><Users size={32} /><h2>No patients found</h2><p>Try a different name or patient ID.</p></div> : null}
    </div>
  );
}
