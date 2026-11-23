import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { ArrowUpRight, Building2, MapPin, X, Bookmark, FileText, ExternalLink } from 'lucide-react'
import { safeExternalUrl } from '../utils/promptBuilder'

const WARNING_TAGS = new Set(['kat_d', 'kat_c', 'udt', 'sanepid', 'noce_weekendy', 'prowizja_scam', 'orzeczenie'])
const DANGER_TAGS = new Set(['brak_widelek'])
const TAG_LABELS = {
  kat_d: 'Kat. D / autobus',
  kat_c: 'Kat. C / ciężarówka',
  udt: 'Uprawnienia UDT',
  sanepid: 'Sanepid',
  noce_weekendy: 'Noce / weekendy',
  prowizja_scam: 'Prowizja / B2B',
  orzeczenie: 'Orzeczenie',
  zlecenie_student: 'Zlecenie dla studenta',
  bez_doswiadczenia: 'Bez doświadczenia',
  brak_widelek: 'Brak widełek',
}

function JobTags({ tags }) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? tags : tags.slice(0, 4)
  return (
    <div className="job-tags" aria-label="Wymagania i cechy oferty">
      {visible.map((tag) => (
        <span className={`job-tag ${DANGER_TAGS.has(tag) ? 'job-tag-missing-salary' : WARNING_TAGS.has(tag) ? 'job-tag-warning' : 'job-tag-positive'}`} key={tag}>
          {TAG_LABELS[tag] || tag.replaceAll('_', ' ')}
        </span>
      ))}
      {tags.length > 4 && (
        <button className="job-tag job-tag-more" type="button" onClick={() => setShowAll((value) => !value)} aria-expanded={showAll}>
          {showAll ? 'Pokaż mniej' : `+${tags.length - 4} więcej`}
        </button>
      )}
      {tags.length === 0 && <span className="job-tag job-tag-neutral">Bez dodatkowych oznaczeń</span>}
    </div>
  )
}

function JobDetails({ job, onClose }) {
  const dialogRef = useRef(null)
  const url = safeExternalUrl(job.url)
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return undefined
    dialog.showModal()
    const close = () => onClose()
    dialog.addEventListener('close', close)
    return () => {
      dialog.removeEventListener('close', close)
      if (dialog.open) dialog.close()
    }
  }, [onClose])

  return (
    <dialog ref={dialogRef} className="details-dialog" aria-labelledby="job-details-title" onClick={(event) => event.target === event.currentTarget && onClose()} onCancel={(event) => { event.preventDefault(); onClose() }}>
      <div className="details-panel">
        <div className="details-topline"><span className="eyebrow">SZCZEGÓŁY OFERTY</span><button className="icon-button" type="button" onClick={onClose} aria-label="Zamknij szczegóły"><X size={19} /></button></div>
        <span className="details-city"><MapPin size={15} /> {job.city} · {job.source}</span>
        <h2 id="job-details-title">{job.title}</h2>
        <p className="details-company"><Building2 size={17} /> {job.company}</p>
        <div className="details-salary">{job.salary?.display_label || 'Stawka nie została podana'}</div>
        <JobTags tags={job.tags || []} />
        <div className="details-description">{job.description || 'Brak dodatkowego opisu oferty.'}</div>
        {url ? <a className="button-primary details-link" href={url} target="_blank" rel="noopener noreferrer">Otwórz ofertę <ExternalLink size={16} /></a> : <p className="unsafe-link-note">Link do oferty nie jest bezpieczny i został ukryty.</p>}
      </div>
    </dialog>
  )
}

function Salary({ salary }) {
  if (!salary) return <div className="salary-pill salary-hidden">STAWKA UKRYTA <span>sprawdź opis</span></div>
  const amount = salary.display_label || [salary.minimum, salary.maximum].filter(Boolean).join('–')
  return (
    <div className="salary-pill">
      <span className="salary-label">STAWKA</span>
      <strong>{amount}</strong>
    </div>
  )
}

function JobCard({ job }) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const demo = job.source?.toLowerCase().includes('demo')
  const showDetails = () => setDetailsOpen(true)
  const closeDetails = useCallback(() => setDetailsOpen(false), [])

  return (
    <>
      <div className="job-card-content">
        <div className="job-card-eyebrow">
          <span className="job-location"><MapPin size={15} />{job.city}</span>
          <span className={`source-label ${demo ? 'source-demo' : ''}`}>
            {demo ? 'DEMO · DANE FIKCYJNE' : job.source}
          </span>
        </div>
        <Salary salary={job.salary} />
        <div className="job-title-area">
          <span className="company-monogram" aria-hidden="true">{job.company?.trim()?.charAt(0)?.toUpperCase() || 'J'}</span>
          <div className="job-heading-copy">
            <h2>{job.title}</h2>
            <p><Building2 size={15} /> {job.company}</p>
          </div>
        </div>
        <JobTags tags={job.tags || []} />
        <div className="job-summary-block">
          <p>{job.summary || 'Brak krótkiego opisu. Otwórz szczegóły, aby sprawdzić ofertę.'}</p>
          <button className="job-details-button" type="button" onClick={showDetails}>
            <FileText size={15} /> Pełny opis i link do oferty <ArrowUpRight size={14} />
          </button>
        </div>
      </div>
      {detailsOpen && <JobDetails job={job} onClose={closeDetails} />}
    </>
  )
}

export default function SwipeDeck({ job, onSwipe, disabled }) {
  return (
    <div className="deck-stage">
      {job && <SwipeCard key={job.hash} job={job} onSwipe={onSwipe} disabled={disabled} />}
    </div>
  )
}

function SwipeCard({ job, onSwipe, disabled }) {
  const x = useMotionValue(0)
  const rotate = useTransform(x, [-260, 260], [-7, 7])
  const opacity = useTransform(x, [-560, -260, 260, 560], [0, 1, 1, 0])
  const rejectOpacity = useTransform(x, [-140, -25], [0.95, 0])
  const saveOpacity = useTransform(x, [25, 140], [0, 0.95])
  const isAnimating = useRef(false)
  const mounted = useRef(false)
  const [swiping, setSwiping] = useState(false)

  useLayoutEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      x.stop()
    }
  }, [x])

  const swipe = useCallback((direction) => {
    if (!mounted.current || disabled || isAnimating.current) return
    isAnimating.current = true
    setSwiping(true)
    animate(x, direction * 560, {
      duration: 0.21,
      ease: 'easeOut',
      onComplete: () => {
        if (mounted.current) onSwipe(direction > 0 ? 'save' : 'dismiss', job)
      },
    })
  }, [disabled, job, onSwipe, x])

  useEffect(() => {
    if (disabled) return undefined
    const onKeyDown = (event) => {
      if (event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      if (document.querySelector('[role="dialog"], dialog[open]')) return
      const target = event.target
      if (target?.isContentEditable || target?.closest?.('input, textarea, select, [contenteditable="true"]')) return
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        swipe(-1)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        swipe(1)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [disabled, swipe])

  const onDragEnd = (_, info) => {
    if (disabled || isAnimating.current) return
    if (info.offset.x > 112 || info.velocity.x > 850) swipe(1)
    else if (info.offset.x < -112 || info.velocity.x < -850) swipe(-1)
  }

  return (
    <>
      <motion.article
        className="job-card"
        drag={disabled || swiping ? false : 'x'}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.82}
        onDragEnd={onDragEnd}
        style={{ x, rotate, opacity }}
        initial={{ y: 16, scale: 0.985 }}
        animate={{ y: 0, scale: 1 }}
        transition={{ duration: 0.18 }}
      >
        <motion.div className="swipe-overlay swipe-reject" style={{ opacity: rejectOpacity }}>ODRZUĆ <X size={18} /></motion.div>
        <motion.div className="swipe-overlay swipe-save" style={{ opacity: saveOpacity }}>ZAPISZ <Bookmark size={17} /></motion.div>
        <JobCard job={job} />
      </motion.article>
      <div className="deck-controls">
        <button className="deck-action action-dismiss" type="button" disabled={disabled || swiping} onClick={() => swipe(-1)} aria-label="Odrzuć tę ofertę">
          <X size={24} strokeWidth={2.5} />
        </button>
        <p>← pomiń <span>·</span> zapisz →</p>
        <button className="deck-action action-save" type="button" disabled={disabled || swiping} onClick={() => swipe(1)} aria-label="Zapisz tę ofertę">
          <Bookmark size={22} strokeWidth={2.5} />
        </button>
      </div>
    </>
  )
}
