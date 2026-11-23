export default function MasterCvEditor({ value, onChange, saveStatus, id }) {
  const saveFailed = saveStatus.includes('nie udało')
  return (
    <section className="sidebar-card cv-panel">
      <h3>Master CV</h3>
      <p>Twoje doświadczenie zostaje w tej przeglądarce. Użyj go do promptu pod konkretną ofertę.</p>
      <label className="sr-only" htmlFor={id}>Treść Master CV — zapisywana tylko lokalnie</label>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Umiejętności, projekty, doświadczenie…"
        rows={4}
        autoComplete="off"
        spellCheck="true"
      />
      <div className={`cv-save-state ${saveFailed ? 'cv-save-state-warning' : ''}`} role="status">{saveStatus}</div>
    </section>
  )
}
