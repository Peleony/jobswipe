import { FileText, LockKeyhole } from 'lucide-react'

export default function MasterCvEditor({ value, onChange, saveStatus, id }) {
  const saveFailed = saveStatus.includes('nie udało')
  return (
    <section className="sidebar-card cv-panel">
      <div className="cv-panel-heading">
        <span className="cv-icon"><FileText size={17} /></span>
        <div><span className="eyebrow">TYLKO U CIEBIE</span><h3>Master CV</h3></div>
      </div>
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
      <div className={`cv-save-state ${saveFailed ? 'cv-save-state-warning' : ''}`} role="status"><span className={`status-dot ${saveStatus.startsWith('Zapisane') ? 'status-green' : ''}`} />{saveStatus}</div>
      <p className="cv-never-sent"><LockKeyhole size={13} /> CV nie trafia do naszego backendu.</p>
    </section>
  )
}
