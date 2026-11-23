import { useEffect, useRef, useState } from 'react'
import { Check, MapPin, RotateCcw, X } from 'lucide-react'
import MasterCvEditor from './MasterCvEditor'
import { DEFAULT_FILTERS, normalizeFilters } from '../utils/storage'

const INDUSTRIES = [
  { id: 'gastro', label: 'Gastronomia' },
  { id: 'magazyn', label: 'Magazyn i logistyka' },
  { id: 'transport', label: 'Transport i dostawy' },
  { id: 'sprzedaz_d2d', label: 'Sprzedaż bezpośrednia' },
]

const BARRIERS = [
  { id: 'kat_d', label: 'Prawo jazdy kat. D / autobus' },
  { id: 'kat_c', label: 'Prawo jazdy kat. C / ciężarówka' },
  { id: 'udt', label: 'Uprawnienia UDT' },
  { id: 'sanepid', label: 'Książeczka sanepidowska' },
  { id: 'noce_weekendy', label: 'Noce i weekendy' },
  { id: 'prowizja_scam', label: 'Prowizja, B2B lub własna działalność' },
  { id: 'orzeczenie', label: 'Wymagane orzeczenie' },
]

const CITIES = ['Kraków', 'Warszawa', 'Wrocław']

function FilterGroup({ title, items, checked, onToggle, note }) {
  return (
    <section className="filter-group">
      <div className="filter-group-heading">
        <h3>{title}</h3>
        {note && <span>{note}</span>}
      </div>
      <div className="filter-options">
        {items.map((item) => {
          const active = checked.includes(item.id)
          return (
            <label className={`filter-option ${active ? 'is-active' : ''}`} key={item.id}>
              <input
                type="checkbox"
                checked={active}
                onChange={() => onToggle(item.id)}
              />
              <span className="filter-check" aria-hidden="true">{active && <Check size={13} />}</span>
              <span>{item.label}</span>
            </label>
          )
        })}
      </div>
    </section>
  )
}

export default function FilterDrawer({
  open,
  filters,
  masterCv,
  cvStatus,
  dismissedCount,
  onMasterCvChange,
  onResetHistory,
  onClose,
  onApply,
}) {
  const [draft, setDraft] = useState(filters)
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const previousFocus = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    previousFocus.current = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const frame = requestAnimationFrame(() => closeRef.current?.focus())
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
      if (event.key !== 'Tab') return
      const elements = dialogRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      )
      if (!elements?.length) return
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      previousFocus.current?.focus?.()
    }
  }, [open, onClose])

  useEffect(() => {
    if (open) setDraft(normalizeFilters(filters))
  }, [open, filters])

  if (!open) return null

  const toggle = (field, value) => {
    setDraft((current) => ({
      ...current,
      [field]: current[field].includes(value)
        ? current[field].filter((item) => item !== value)
        : [...current[field], value],
    }))
  }

  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        className="filter-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="filter-title"
        ref={dialogRef}
      >
        <header className="drawer-header">
          <div>
            <span className="eyebrow">USTAW PO SWOJEMU</span>
            <h2 id="filter-title">Twój filtr na ściemę</h2>
            <p>Ty decydujesz, co zostaje poza talią.</p>
          </div>
          <button ref={closeRef} className="icon-button" onClick={onClose} aria-label="Zamknij filtry">
            <X size={20} />
          </button>
        </header>

        <div className="drawer-content">
          <section className="filter-group">
            <div className="filter-group-heading"><h3>Miasto</h3><span>możesz też wpisać własne</span></div>
            <label className="city-input-wrap">
              <MapPin size={17} aria-hidden="true" />
              <span className="sr-only">Filtruj po mieście</span>
              <input
                value={draft.city}
                onChange={(event) => setDraft((current) => ({ ...current, city: event.target.value }))}
                placeholder="Każde miasto"
              />
              {draft.city && <button type="button" onClick={() => setDraft((current) => ({ ...current, city: '' }))} aria-label="Wyczyść miasto"><X size={15} /></button>}
            </label>
            <div className="city-chips" aria-label="Popularne miasta">
              {CITIES.map((city) => (
                <button
                  className={`city-chip ${draft.city === city ? 'selected' : ''}`}
                  key={city}
                  type="button"
                  onClick={() => setDraft((current) => ({ ...current, city: current.city === city ? '' : city }))}
                >
                  {city}
                </button>
              ))}
            </div>
          </section>

          <label className="salary-toggle">
            <span className="toggle-copy"><strong>Pokazuj tylko oferty ze stawką</strong><small>Domyślnie ukrywamy niejasne wynagrodzenie.</small></span>
            <input
              type="checkbox"
              checked={draft.require_salary}
              onChange={(event) => setDraft((current) => ({ ...current, require_salary: event.target.checked }))}
            />
            <span className="switch-track" aria-hidden="true"><span /></span>
          </label>

          <FilterGroup
            title="Branże poza talią"
            note="nic nie blokujemy domyślnie"
            items={INDUSTRIES}
            checked={draft.blocked_industries}
            onToggle={(value) => toggle('blocked_industries', value)}
          />

          <FilterGroup
            title="Wymagania poza talią"
            note="możesz je odblokować"
            items={BARRIERS}
            checked={draft.blocked_tags}
            onToggle={(value) => toggle('blocked_tags', value)}
          />

          <p className="default-filter-note">
            <span>Domyślne ustawienia ukrywają kat. C/D i oferty prowizyjne. To tylko praktyczne oznaczenia z opisu — nie są oceną ani dowodem nadużycia.</span>
          </p>

          <MasterCvEditor
            id="master-cv-drawer"
            value={masterCv}
            onChange={onMasterCvChange}
            saveStatus={cvStatus}
          />

          <section className="drawer-history">
            <h3>Historia odrzuceń</h3>
            <p>{dismissedCount
              ? `${dismissedCount} pominiętych ofert. Reset przywraca je do odkrywania; zapisane oferty pozostają bez zmian.`
              : 'Historia jest pusta. Reset nie usuwa zapisanych ofert.'}</p>
            <button className="text-button" type="button" onClick={onResetHistory} disabled={!dismissedCount}>
              <RotateCcw size={14} /> Resetuj historię odrzuceń
            </button>
          </section>
        </div>

        <footer className="drawer-footer">
          <button className="text-button" type="button" onClick={() => setDraft({ ...DEFAULT_FILTERS, blocked_tags: [...DEFAULT_FILTERS.blocked_tags], blocked_industries: [] })}>
            <RotateCcw size={15} /> Przywróć domyślne
          </button>
          <button className="button-primary" type="button" onClick={() => onApply(normalizeFilters(draft))}>
            Pokaż oferty
          </button>
        </footer>
      </section>
    </div>
  )
}
