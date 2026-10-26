"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, ClipboardList, LogOut, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { z } from "zod";

const ClinicianSchema = z.object({ id: z.string(), name: z.string(), role: z.string(), clinic: z.string() });
const navItems = [
  { href: "/queue", label: "Priority queue", icon: Activity },
  { href: "/patients", label: "Patients", icon: Users },
  { href: "/rules", label: "Rules", icon: ClipboardList },
  { href: "/demo", label: "Demo controls", icon: Activity },
];

export default function ConsoleLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const pathname = usePathname();
  const [clinician, setClinician] = useState<z.infer<typeof ClinicianSchema> | null>(null);
  const [demoTime, setDemoTime] = useState("");
  useEffect(() => {
    const update = () => api("/demo/state", z.object({ now: z.string() })).then(state => setDemoTime(new Date(state.now).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))).catch(() => undefined);
    void update();
    const timer = setInterval(() => void update(), 15000);
    return () => clearInterval(timer);
  }, []);
  const [checking, setChecking] = useState(true);
  useEffect(() => {
    let active = true;
    api("/auth/me", ClinicianSchema)
      .then((user) => { if (active) setClinician(user); })
      .catch(() => { if (active) router.replace("/login"); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [router]);

  async function logout() {
    await api("/auth/logout", z.undefined(), { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  if (checking || !clinician) {
    return <main className="loading-screen" aria-live="polite">Checking demo clinician session…</main>;
  }
  return (
    <div className="console-shell">
      <div className="ribbon">SYNTHETIC DATA · PROTOTYPE · NOT FOR CLINICAL USE</div>
      <div className="console-frame">
        <aside className="sidebar" aria-label="Main navigation">
          <Link className="brand" href="/queue">Setu<span>care continuity</span></Link>
          <div className="clinic-label">DEMO CLINIC</div>
          <nav className="nav-list">
            {navItems.map(({ href, label, icon: Icon }) => (
              <Link key={href} className={`nav-link ${pathname.startsWith(href) ? "active" : ""}`} href={href}>
                <Icon size={18} aria-hidden="true" /><span>{label}</span>
              </Link>
            ))}
          </nav>
          <div className="sidebar-note"><span className="live-dot" /> Offline mock AI ready</div>
        </aside>
        <div className="console-main">
          <header className="console-topbar">
            <span className="topbar-context">{demoTime ? `${demoTime} IST · demo clock` : "Post-discharge care"}</span>
            <div className="clinician-menu"><span className="clinician-avatar">{clinician.name.slice(0, 1)}</span><span>{clinician.name}</span>
              <button className="icon-button" type="button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
            </div>
          </header>
          <main className="console-content">{children}</main>
        </div>
      </div>
    </div>
  );
}
