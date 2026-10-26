"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api, ApiError, jsonBody } from "@/lib/api";

const LoginResultSchema = z.object({ clinician: z.object({ id: z.string(), name: z.string(), role: z.string() }) });

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("dr.anitha@demo.setu");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/auth/login", LoginResultSchema, jsonBody({ email, password }));
      router.replace("/queue");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not sign in. Check the API is running.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <div className="ribbon">SYNTHETIC DATA · PROTOTYPE · NOT FOR CLINICAL USE</div>
      <section className="login-card" aria-labelledby="login-title">
        <Link className="brand" href="/">Setu<span>care continuity</span></Link>
        <p className="eyebrow">CLINICIAN CONSOLE</p>
        <h1 id="login-title">Sign in to your care queue.</h1>
        <p className="login-intro">Use the demo clinician account to review synthetic patient follow-ups.</p>
        <form onSubmit={submit} className="form-stack">
          <label>Email<input autoComplete="username" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label>Password<input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <button className="primary-button full-width" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="demo-credentials">Demo account: dr.anitha@demo.setu · demo123</p>
      </section>
    </main>
  );
}
