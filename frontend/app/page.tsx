function SyntheticRibbon() {
  return <div className="ribbon">SYNTHETIC DATA · DEMO ONLY · NOT FOR CLINICAL USE</div>;
}

export default function HomePage() {
  return (
    <main className="shell">
      <SyntheticRibbon />
      <header className="topbar">
        <a className="brand" href="/">Setu<span>care continuity</span></a>
        <span className="environment">DEMO CONSOLE</span>
      </header>
      <section className="welcome" aria-labelledby="welcome-title">
        <p className="eyebrow">POST-DISCHARGE CARE</p>
        <h1 id="welcome-title">The care between visits.</h1>
        <p className="intro">A clinician-led view of patient check-ins, care plans, and follow-up needs.</p>
        <div className="empty-card">
          <div className="pulse" aria-hidden="true">↗</div>
          <div>
            <h2>Your console is ready</h2>
            <p>Patient and alert workflows will appear here as the prototype is built.</p>
          </div>
          <span className="status">SCAFFOLD</span>
        </div>
      </section>
      <footer>Automate the gaps, never the doctor.</footer>
    </main>
  );
}
