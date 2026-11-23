export const STORAGE_KEYS = {
  filters: 'jobswipe.filters.v1',
  saved: 'jobswipe.saved.v1',
  dismissed: 'jobswipe.dismissed.v1',
  masterCv: 'jobswipe.masterCv.v1',
}

export const DEFAULT_FILTERS = {
  city: '',
  blocked_tags: ['kat_d', 'kat_c', 'prowizja_scam'],
  blocked_industries: [],
  require_salary: true,
}

export function readStored(key, fallback, storage) {
  try {
    const value = (storage ?? globalThis.localStorage)?.getItem(key)
    if (value === null || value === undefined) return fallback
    const parsed = JSON.parse(value)
    if (Array.isArray(fallback) && !Array.isArray(parsed)) return fallback
    if (typeof fallback === 'string' && typeof parsed !== 'string') return fallback
    if (fallback && typeof fallback === 'object' && !Array.isArray(fallback)) {
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fallback
    }
    return parsed
  } catch {
    return fallback
  }
}

export function writeStored(key, value, storage) {
  try {
    const target = storage ?? globalThis.localStorage
    if (!target || typeof target.setItem !== 'function') return false
    target.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export function normalizeFilters(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return DEFAULT_FILTERS
  return {
    city: typeof value.city === 'string' ? value.city : DEFAULT_FILTERS.city,
    blocked_tags: Array.isArray(value.blocked_tags)
      ? value.blocked_tags.filter((item) => typeof item === 'string')
      : [...DEFAULT_FILTERS.blocked_tags],
    blocked_industries: Array.isArray(value.blocked_industries)
      ? value.blocked_industries.filter((item) => typeof item === 'string')
      : [],
    require_salary: typeof value.require_salary === 'boolean'
      ? value.require_salary
      : DEFAULT_FILTERS.require_salary,
  }
}

export function normalizeSavedJobs(value) {
  if (!Array.isArray(value)) return []
  return value.filter((job) =>
    job && typeof job === 'object' && !Array.isArray(job) &&
    ['hash', 'title', 'company', 'city', 'url'].every((key) => typeof job[key] === 'string'),
  )
}

export function normalizeDismissedHashes(value) {
  return Array.isArray(value) ? value.filter((hash) => typeof hash === 'string') : []
}
