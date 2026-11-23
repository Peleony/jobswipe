import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, ArrowDown, ArrowLeft, ArrowRight, Bookmark, BriefcaseBusiness, ChevronRight,
  CircleHelp, Layers3, LockKeyhole, MapPin, RefreshCw, RotateCcw,
  ShieldCheck, SlidersHorizontal, Sparkles,
} from 'lucide-react'
import FilterDrawer from './components/FilterDrawer'
import MasterCvEditor from './components/MasterCvEditor'
import SavedList from './components/SavedList'
import SwipeDeck from './components/SwipeDeck'
import Toast from './components/Toast'
import { filterJobsForCurrentExclusions, hasFullJobBatch } from './utils/jobBatches'
import { buildCvPrompt, copyText } from './utils/promptBuilder'
import { DEFAULT_FILTERS, normalizeDismissedHashes, normalizeFilters, normalizeSavedJobs, readStored, STORAGE_KEYS, writeStored } from './utils/storage'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

function IconMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span className="brand-card brand-card-back" />
      <span className="brand-card brand-card-front"><Layers3 size={20} strokeWidth={2.5} /></span>
    </span>
  )
}

function FilterSummary({ filters, onEdit }) {
  const labels = {
    kat_d: 'Kat. D', kat_c: 'Kat. C', udt: 'UDT', sanepid: 'Sanepid',
    noce_weekendy: 'Noce / weekendy', prowizja_scam: 'Prowizja / B2B', orzeczenie: 'Orzeczenie',
    gastro: 'Gastronomia', magazyn: 'Magazyn', transport: 'Transport', sprzedaz_d2d: 'Sprzedaż D2D',
  }
  const selected = [...filters.blocked_tags, ...filters.blocked_industries]

  return (
    <aside className="sidebar-card filter-summary-card">
      <span className="eyebrow">TWÓJ ZESTAW ZASAD</span>
      <h2>Twój filtr<br />na ściemę<span>.</span></h2>
      <div className="summary-city">
        <MapPin size={15} />
        <span>{filters.city || 'Cała Polska'}</span>
      </div>
      <div className="summary-divider" />
      <p className="summary-caption">Poza talią</p>
      {selected.length ? (
        <div className="summary-chips">
          {selected.slice(0, 5).map((item) => <span className="summary-chip" key={item}>{labels[item] || item}</span>)}
          {selected.length > 5 && <span className="summary-chip summary-chip-muted">+{selected.length - 5}</span>}
        </div>
      ) : <p className="summary-no-filters">Nie pomijamy żadnych branż ani wymagań.</p>}
      <p className="salary-summary"><span className={filters.require_salary ? 'status-dot status-green' : 'status-dot'} />
        {filters.require_salary ? 'Tylko oferty ze stawką' : 'Także bez podanej stawki'}
      </p>
      <button type="button" className="button-secondary summary-edit" onClick={onEdit}>
        <SlidersHorizontal size={15} /> Dostosuj filtry
      </button>
      <div className="how-to-swipe">
        <span className="eyebrow">JAK TO DZIAŁA</span>
        <p><ArrowLeft size={14} /> W lewo — pomijasz</p>
        <p><ArrowRight size={14} /> W prawo — zapisujesz</p>
      </div>
    </aside>
  )
}

function PrivacyCard({ onResetHistory, dismissedCount, storageWarning }) {
  return (
    <section className="sidebar-card privacy-card">
      <div className="privacy-icon"><ShieldCheck size={18} /></div>
      <span className="eyebrow">TWOJE DANE, TWOJA SPRAWA</span>
      <h3>Bez konta.<br />Bez śledzenia.</h3>
      <p>{storageWarning
        ? 'Nie udało się zapisać części zmian w przeglądarce. Mogą zniknąć po odświeżeniu.'
        : 'Zapisane oferty, filtry i Master CV są tylko na tym urządzeniu. Wysyłamy do backendu wyłącznie filtry i identyfikatory ofert już zapisanych lub pominiętych.'}</p>
      <div className="privacy-divider" />
      <p className="ai-note"><Sparkles size={14} /> Prompt kopiujesz do własnego AI. Nie łączymy się z żadnym modelem.</p>
      <button className="text-button history-reset" type="button" onClick={onResetHistory} disabled={!dismissedCount}>
        <RotateCcw size={14} /> Resetuj historię odrzuceń
      </button>
      <span className="history-count">{dismissedCount ? `${dismissedCount} pominiętych lokalnie` : 'Historia odrzuceń jest pusta'}</span>
    </section>
  )
}

function LoadingCard() {
  return (
    <div className="loading-card" aria-label="Ładowanie ofert" role="status">
      <span className="skeleton skeleton-eyebrow" />
      <span className="skeleton skeleton-salary" />
      <span className="skeleton skeleton-title" />
      <span className="skeleton skeleton-company" />
      <span className="skeleton skeleton-tags" />
      <span className="skeleton skeleton-copy" />
      <span className="skeleton skeleton-copy short" />
    </div>
  )
}

function NoJobs({ error, onRetry, onRefresh, onFilters, onResetHistory, dismissedCount, refreshing }) {
  if (error) {
    return (
      <div className="empty-deck error-deck" role="alert">
        <span className="empty-icon"><CircleHelp size={22} /></span>
        <span className="eyebrow">COŚ POSZŁO NIE TAK</span>
        <h2>Nie udało się pobrać ofert.</h2>
        <p>{error}</p>
        <button className="button-primary" type="button" onClick={onRetry}><RefreshCw size={16} /> Spróbuj ponownie</button>
      </div>
    )
  }
  return (
    <div className="empty-deck">
      <span className="empty-icon"><BriefcaseBusiness size={22} /></span>
      <span className="eyebrow">KONIEC TALII</span>
      <h2>Na teraz to wszystko.</h2>
      <p>Spróbuj zmienić filtry albo pobierz najnowsze oferty.</p>
      <div className="empty-actions">
        <button className="button-primary" type="button" onClick={onFilters}><SlidersHorizontal size={15} /> Zmień filtry</button>
        <button className="button-secondary" type="button" onClick={onRefresh} disabled={refreshing}><RefreshCw size={15} /> Odśwież oferty</button>
      </div>
      {dismissedCount > 0 && <button className="text-button" type="button" onClick={onResetHistory}>Pokaż ponownie pominięte ({dismissedCount})</button>}
    </div>
  )
}

function App() {
  const [filters, setFilters] = useState(() => normalizeFilters(readStored(STORAGE_KEYS.filters, DEFAULT_FILTERS)))
  const [saved, setSaved] = useState(() => normalizeSavedJobs(readStored(STORAGE_KEYS.saved, [])))
  const [dismissed, setDismissed] = useState(() => normalizeDismissedHashes(readStored(STORAGE_KEYS.dismissed, [])))
  const [masterCv, setMasterCv] = useState(() => readStored(STORAGE_KEYS.masterCv, ''))
  const [cvStatus, setCvStatus] = useState('Sprawdzam zapis lokalny…')
  const [activeTab, setActiveTab] = useState('discover')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const [toast, setToast] = useState(null)
  const [storageFailures, setStorageFailures] = useState([])
  const toastTimer = useRef(null)
  const savedRef = useRef(saved)
  const dismissedRef = useRef(dismissed)
  const refillInFlightRef = useRef(false)
  savedRef.current = saved
  dismissedRef.current = dismissed

  const notify = useCallback((message, type = 'success') => {
    window.clearTimeout(toastTimer.current)
    setToast({ message, type })
    toastTimer.current = window.setTimeout(() => setToast(null), 5000)
  }, [])

  const persist = useCallback((key, value, label) => {
    const stored = writeStored(key, value)
    setStorageFailures((current) => stored
      ? current.filter((failedKey) => failedKey !== key)
      : current.includes(key) ? current : [...current, key])
    if (!stored) {
      notify(`${label}: nie udało się zapisać zmian lokalnie. Mogą zniknąć po odświeżeniu.`, 'error')
    }
    return stored
  }, [notify])

  useEffect(() => { persist(STORAGE_KEYS.filters, filters, 'Filtry') }, [filters, persist])
  useEffect(() => { persist(STORAGE_KEYS.saved, saved, 'Zapisane oferty') }, [saved, persist])
  useEffect(() => { persist(STORAGE_KEYS.dismissed, dismissed, 'Historia odrzuceń') }, [dismissed, persist])

  useEffect(() => () => window.clearTimeout(toastTimer.current), [])

  useEffect(() => {
    const controller = new AbortController()
    const loadJobs = async () => {
      refillInFlightRef.current = true
      setLoading(true)
      setError('')
      setHasMore(false)
      const params = new URLSearchParams()
      if (filters.city.trim()) params.set('city', filters.city.trim())
      params.set('require_salary', String(filters.require_salary))
      filters.blocked_tags.forEach((tag) => params.append('blocked_tags[]', tag))
      filters.blocked_industries.forEach((industry) => params.append('blocked_industries[]', industry))
      const excluded = new Set([
        ...savedRef.current.map((job) => job.hash),
        ...dismissedRef.current,
      ])
      excluded.forEach((hash) => params.append('exclude_hashes[]', hash))
      try {
        const response = await fetch(`${API_BASE}/jobs?${params.toString()}`, { signal: controller.signal })
        if (!response.ok) throw new Error(`Serwer odpowiedział błędem ${response.status}.`)
        const result = await response.json()
        if (!Array.isArray(result)) throw new Error('Serwer zwrócił nieprawidłową listę ofert.')
        setJobs(filterJobsForCurrentExclusions(result, savedRef.current, dismissedRef.current))
        setHasMore(hasFullJobBatch(result))
      } catch (fetchError) {
        if (fetchError.name !== 'AbortError') {
          setError(fetchError.message || 'Sprawdź połączenie z backendem.')
          setJobs([])
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
          refillInFlightRef.current = false
        }
      }
    }
    loadJobs()
    return () => {
      controller.abort()
      refillInFlightRef.current = false
    }
  }, [filters, reloadToken])

  useEffect(() => {
    if (activeTab !== 'discover' || drawerOpen || loading || error || jobs.length || !hasMore || refillInFlightRef.current) return
    refillInFlightRef.current = true
    setReloadToken((value) => value + 1)
  }, [activeTab, drawerOpen, error, hasMore, jobs.length, loading])

  useEffect(() => {
    let timer
    const stored = persist(STORAGE_KEYS.masterCv, masterCv, 'Master CV')
    setCvStatus(stored ? 'Zapisane na tym urządzeniu' : 'Nie udało się zapisać Master CV')
    if (stored && masterCv) {
      setCvStatus('Zapisuję lokalnie…')
      timer = window.setTimeout(() => setCvStatus('Zapisane na tym urządzeniu'), 450)
    }
    return () => window.clearTimeout(timer)
  }, [masterCv, persist])

  const applyFilters = useCallback((nextFilters) => {
    setFilters(normalizeFilters(nextFilters))
    setDrawerOpen(false)
  }, [])
  const closeFilterDrawer = useCallback(() => setDrawerOpen(false), [])

  const clearDismissed = useCallback(() => {
    dismissedRef.current = []
    setDismissed([])
    setJobs([])
    setReloadToken((value) => value + 1)
    notify('Historia wyczyszczona. Zapisane oferty pozostały bez zmian.')
  }, [notify])

  const refreshListings = useCallback(async () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      const response = await fetch(`${API_BASE}/jobs/refresh`, { method: 'POST' })
      if (!response.ok) throw new Error(`Odświeżenie zakończone błędem ${response.status}.`)
      const result = await response.json()
      setReloadToken((value) => value + 1)
      const count = result.inserted + result.updated
      const providerIssue = result.provider_errors?.length
      notify(
        providerIssue
          ? `Zaktualizowano ${count} ofert. Część źródeł jest chwilowo niedostępna.`
          : `Oferty odświeżone · ${count} dostępnych w bazie.`,
        providerIssue ? 'error' : 'success',
      )
    } catch (refreshError) {
      notify(refreshError.message || 'Nie udało się odświeżyć ofert.', 'error')
    } finally {
      setRefreshing(false)
    }
  }, [notify, refreshing])

  const handleSwipe = useCallback((action, job) => {
    setJobs((current) => current.filter((item) => item.hash !== job.hash))
    if (action === 'save') {
      const nextSaved = savedRef.current.some((item) => item.hash === job.hash)
        ? savedRef.current
        : [job, ...savedRef.current]
      savedRef.current = nextSaved
      setSaved(nextSaved)
      notify('Oferta dodana do zakładki Zapisane.')
    } else {
      const nextDismissed = dismissedRef.current.includes(job.hash)
        ? dismissedRef.current
        : [...dismissedRef.current, job.hash]
      dismissedRef.current = nextDismissed
      setDismissed(nextDismissed)
    }
  }, [notify])

  const removeSaved = useCallback((job) => {
    const nextSaved = savedRef.current.filter((item) => item.hash !== job.hash)
    savedRef.current = nextSaved
    setSaved(nextSaved)
    notify('Oferta usunięta z zapisanych.')
  }, [notify])

  const copyJobPrompt = useCallback(async (job) => {
    try {
      await copyText(buildCvPrompt(masterCv, job))
      notify(masterCv.trim()
        ? 'Prompt skopiowany. Wklej go do wybranego asystenta AI.'
        : 'Prompt skopiowany. Dodaj Master CV, aby dopasować go do swojej historii.')
    } catch {
      notify('Nie udało się skopiować promptu. Sprawdź uprawnienia schowka.', 'error')
    }
  }, [masterCv, notify])

  const dismissCount = dismissed.length
  const frontJob = jobs[0]

  return (
    <div className="app-shell min-h-screen">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="JobSwipe — strona główna" onClick={(event) => { event.preventDefault(); setActiveTab('discover') }}>
          <IconMark />
          <span className="brand-copy"><strong>JobSwipe</strong><small>MNIEJ SZUMU. WIĘCEJ PRACY.</small></span>
        </a>
        <nav className="main-nav" aria-label="Główna nawigacja">
          <button className={`nav-tab ${activeTab === 'discover' ? 'active' : ''}`} type="button" aria-current={activeTab === 'discover' ? 'page' : undefined} onClick={() => setActiveTab('discover')}>
            Odkrywaj
          </button>
          <button className={`nav-tab ${activeTab === 'saved' ? 'active' : ''}`} type="button" aria-current={activeTab === 'saved' ? 'page' : undefined} onClick={() => setActiveTab('saved')}>
            Zapisane <span className="saved-count">{saved.length}</span>
          </button>
        </nav>
        <div className="topbar-actions">
          <span className={`privacy-status ${storageFailures.length ? 'privacy-status-warning' : ''}`}>
            {storageFailures.length ? <AlertTriangle size={14} /> : <LockKeyhole size={14} />}
            {storageFailures.length ? 'Zapis lokalny niedostępny' : 'Twoje dane są lokalnie'}
          </span>
          <button className="top-filter-button" type="button" onClick={() => setDrawerOpen(true)} aria-label="Otwórz filtry">
            <SlidersHorizontal size={17} /><span>Filtry</span>
            {(filters.blocked_tags.length + filters.blocked_industries.length + Number(filters.require_salary) + Number(!!filters.city)) > 0 && <i aria-label="Aktywne filtry" />}
          </button>
        </div>
      </header>

      {storageFailures.length > 0 && (
        <div className="storage-warning-banner" role="alert">
          <AlertTriangle size={16} />
          Nie udało się zapisać części zmian lokalnie. Mogą zniknąć po odświeżeniu.
        </div>
      )}

      <section className="hero-section" id="home">
        <div className="hero-copy">
          <span className="hero-overline"><span className="hero-dot" /> PRACA DLA STUDENTÓW I NA START</span>
          <h1>Twoja praca.<br /><span>Twoje zasady.</span></h1>
          <p>Przesuń oferty, pomiń ściemę. Znajdź pracę, która pasuje do Ciebie.</p>
        </div>
        <div className="demo-indicator"><span className="demo-indicator-dot" /><span>WERSJA DEMO</span><small>fikcyjne przykładowe oferty</small></div>
      </section>

      {activeTab === 'discover' ? (
        <main className="discover-layout">
          <FilterSummary filters={filters} onEdit={() => setDrawerOpen(true)} />

          <section className="discover-center" aria-label="Odkrywaj oferty pracy">
            <div className="deck-heading">
              <div><span className="eyebrow">TWOJA TALIA</span><h2>Może coś dla Ciebie.</h2></div>
              <button className="refresh-button" type="button" onClick={refreshListings} disabled={refreshing} aria-label="Odśwież oferty z backendu">
                <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
                <span>{refreshing ? 'Odświeżam…' : 'Odśwież'}</span>
              </button>
            </div>
            <div className="deck-count-row"><span>{loading ? 'Szukamy ofert…' : `${jobs.length} ${jobs.length === 1 ? 'oferta' : 'ofert'} w talii`}</span><span className="deck-tip"><ArrowDown size={13} /> Przeciągnij kartę, by zdecydować</span></div>
            {loading ? <LoadingCard /> : frontJob ? (
              <SwipeDeck job={frontJob} onSwipe={handleSwipe} disabled={loading} />
            ) : (
              <NoJobs
                error={error}
                onRetry={() => setReloadToken((value) => value + 1)}
                onRefresh={refreshListings}
                onFilters={() => setDrawerOpen(true)}
                onResetHistory={clearDismissed}
                dismissedCount={dismissCount}
                refreshing={refreshing}
              />
            )}
            <p className="keyboard-note"><kbd>←</kbd> pomiń <span>·</span> zapisz <kbd>→</kbd><span className="keyboard-note-extra"> · albo użyj przycisków</span></p>
            {error && !loading && <button className="inline-retry" type="button" onClick={() => setReloadToken((value) => value + 1)}>Spróbuj pobrać ponownie</button>}
          </section>

          <aside className="right-sidebar">
            <section className="sidebar-card saved-preview-card">
              <div className="saved-preview-header"><span className="eyebrow">NA PÓŹNIEJ</span><Bookmark size={17} /></div>
              <h3>{saved.length ? 'To już Twoje.' : 'Coś Cię zaciekawiło?'}</h3>
              {saved.length ? (
                <>
                  <p className="saved-preview-count">{saved.length} zapisanych ofert</p>
                  <div className="saved-preview-items">
                    {saved.slice(0, 2).map((job) => <div className="saved-preview-job" key={job.hash}><span>{job.title}</span><small>{job.city}</small></div>)}
                    {saved.length > 2 && <span className="preview-more">+{saved.length - 2} więcej</span>}
                  </div>
                  <button className="text-button preview-open" type="button" onClick={() => setActiveTab('saved')}>Zobacz zapisane <ChevronRight size={15} /></button>
                </>
              ) : <p>Przesuń kartę w prawo, żeby wrócić do niej później.</p>}
            </section>

            <MasterCvEditor id="master-cv-sidebar" value={masterCv} onChange={setMasterCv} saveStatus={cvStatus} />
            <PrivacyCard onResetHistory={clearDismissed} dismissedCount={dismissCount} storageWarning={storageFailures.length > 0} />
          </aside>
        </main>
      ) : (
        <main className="saved-page">
          <div className="saved-page-heading">
            <div><span className="eyebrow">TWOJA LISTA</span><h2>Zapisane oferty<span>.</span></h2><p>Oferty zapisane lokalnie — na później, bez konta.</p></div>
            <button className="button-secondary" type="button" onClick={() => setActiveTab('discover')}><ArrowLeft size={15} /> Wróć do odkrywania</button>
          </div>
          <SavedList jobs={saved} onRemove={removeSaved} onCopy={copyJobPrompt} />
        </main>
      )}

      <footer className="site-footer">
        <span><IconMark /> JobSwipe <i>·</i> mniej szumu, więcej pracy</span>
        <span><LockKeyhole size={13} /> Konto nie jest potrzebne. Twoje CV nie opuszcza przeglądarki.</span>
      </footer>

      <FilterDrawer
        open={drawerOpen}
        filters={filters}
        masterCv={masterCv}
        cvStatus={cvStatus}
        dismissedCount={dismissCount}
        onMasterCvChange={setMasterCv}
        onResetHistory={clearDismissed}
        onClose={closeFilterDrawer}
        onApply={applyFilters}
      />
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}

export default App
