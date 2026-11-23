import { Bookmark, Building2, Copy, ExternalLink, MapPin, Trash2 } from 'lucide-react'
import { safeExternalUrl } from '../utils/promptBuilder'

const TAG_LABELS = {
  kat_d: 'Kat. D', kat_c: 'Kat. C', udt: 'UDT', sanepid: 'Sanepid',
  noce_weekendy: 'Noce / weekendy', prowizja_scam: 'Prowizja / B2B',
  orzeczenie: 'Orzeczenie', zlecenie_student: 'Zlecenie dla studenta',
  bez_doswiadczenia: 'Bez doświadczenia',
  brak_widelek: 'Brak widełek',
}

export default function SavedList({ jobs, onRemove, onCopy }) {
  if (!jobs.length) {
    return (
      <div className="saved-empty">
        <span className="empty-icon"><Bookmark size={23} /></span>
        <span className="eyebrow">NA PÓŹNIEJ</span>
        <h2>Tu trafiają oferty warte drugiego spojrzenia.</h2>
        <p>Przesuń kartę w prawo albo wybierz zakładkę Odkrywaj i zapisz coś dla siebie.</p>
      </div>
    )
  }

  return (
    <div className="saved-list">
      {jobs.map((job) => {
        const url = safeExternalUrl(job.url)
        return (
          <article className="saved-card" key={job.hash}>
            <div className="saved-card-head">
              <span className="saved-city"><MapPin size={14} /> {job.city}</span>
              <button className="icon-button saved-remove" type="button" onClick={() => onRemove(job)} aria-label={`Usuń ${job.title} z zapisanych`}>
                <Trash2 size={17} />
              </button>
            </div>
            <h3>{job.title}</h3>
            <p className="saved-company"><Building2 size={15} /> {job.company}</p>
            <div className={job.salary ? 'saved-salary' : 'saved-salary salary-hidden-text'}>
              {job.salary?.display_label || 'Stawka ukryta'}
            </div>
            {job.source?.toLowerCase().includes('demo') && <span className="saved-demo">DEMO · DANE FIKCYJNE</span>}
            {!!job.tags?.length && <div className="saved-tags">{job.tags.slice(0, 5).map((tag) => <span className={tag === 'brak_widelek' ? 'saved-tag-missing-salary' : ''} key={tag}>{TAG_LABELS[tag] || tag}</span>)}</div>}
            <p className="saved-summary">{job.summary || job.description}</p>
            <div className="saved-card-actions">
              {url ? <a className="button-secondary" href={url} target="_blank" rel="noopener noreferrer">Otwórz ofertę <ExternalLink size={15} /></a> : <span className="unsafe-link-note">Niebezpieczny link ukryty</span>}
              <button className="button-secondary" type="button" onClick={() => onCopy(job)}><Copy size={15} /> Kopiuj prompt pod CV</button>
            </div>
          </article>
        )
      })}
    </div>
  )
}
