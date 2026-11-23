import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { describe, expect, it, vi } from 'vitest'
import App, { formatRefreshNotification } from './App'
import { STORAGE_KEYS } from './utils/storage'

it('searches with filters and history hashes only and identifies a full batch', async () => {
  const saved = {
    hash: '0123456789abcdef', title: 'Zapisana oferta', company: 'Firma',
    city: 'Kraków', url: 'https://example.org/saved',
  }
  const dismissed = 'fedcba9876543210'
  const jobs = Array.from({ length: 50 }, (_, index) => ({
    ...saved, hash: (index + 1).toString(16).padStart(16, '0'), title: 'Nowa oferta',
    tags: [], industries: [], summary: '', description: '', source: 'Jooble',
  }))
  localStorage.setItem(STORAGE_KEYS.saved, JSON.stringify([saved]))
  localStorage.setItem(STORAGE_KEYS.dismissed, JSON.stringify([dismissed]))
  localStorage.setItem(STORAGE_KEYS.masterCv, JSON.stringify('Prywatne CV'))
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const fetchJobs = vi.fn().mockResolvedValue({ ok: true, json: async () => jobs })
  vi.stubGlobal('fetch', fetchJobs)
  const container = document.createElement('div')
  const root = createRoot(container)
  try {
    await act(async () => root.render(<App />))
    expect(fetchJobs).toHaveBeenCalledTimes(1)
    const [url, options] = fetchJobs.mock.calls[0]
    expect(url).toBe('/api/jobs/search')
    expect(options.method).toBe('POST')
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(options.body)).toEqual({
      city: '', require_salary: true, blocked_tags: ['kat_d', 'kat_c', 'prowizja_scam'],
      blocked_industries: [], exclude_hashes: [saved.hash, dismissed],
    })
    expect(container.querySelector('.deck-heading p').textContent).toBe('W partii: 50 · kolejna automatycznie')
  } finally {
    await act(() => root.unmount())
    localStorage.clear()
    vi.unstubAllGlobals()
  }
})

describe('formatRefreshNotification', () => {
  it('keeps the batch notice to database counts and the next step', () => {
    const notification = formatRefreshNotification({
      fetched: 380,
      inserted: 24,
      updated: 3,
      total: 71,
      provider_errors: [],
      jooble: {
        results_received: 400,
        requests_this_refresh: 20,
        requests_today: 20,
        daily_request_limit: 90,
        status: 'batch_complete',
        paused_reason: 'Kliknij Odśwież, aby pobrać następną partię.',
      },
    })

    expect(notification.type).toBe('success')
    expect(notification.message).toBe(
      'Dodano 24, zaktualizowano 3; w bazie: 71. Odśwież ponownie, aby pobrać kolejną partię.',
    )
  })

  it('reports partial imports and a safe provider pause as an error notice', () => {
    const notification = formatRefreshNotification({
      fetched: 20,
      inserted: 15,
      updated: 1,
      total: 66,
      provider_errors: ['jooble: Jooble returned HTTP 403'],
      jooble: {
        results_received: 20,
        requests_this_refresh: 2,
        requests_today: 8,
        daily_request_limit: 90,
        status: 'access_denied',
        paused_reason: 'Jooble zwrócił HTTP 403. Sprawdź klucz.',
      },
    })

    expect(notification.type).toBe('error')
    expect(notification.message).toBe(
      'Dodano 15, zaktualizowano 1; w bazie: 66. Jooble odmówił dostępu (HTTP 403).',
    )
  })
})
