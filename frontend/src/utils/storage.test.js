import { describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS, normalizeDismissedHashes, normalizeFilters, normalizeSavedJobs, readStored, writeStored } from './storage'

function failingStorage() {
  return {
    getItem() { throw new Error('blocked') },
    setItem() { throw new Error('quota') },
  }
}

describe('local state storage', () => {
  it('safely returns the fallback for invalid JSON and unavailable storage', () => {
    const storage = { getItem: () => '{broken' }
    expect(readStored('jobswipe.saved.v1', [], storage)).toEqual([])
    expect(readStored('jobswipe.filters.v1', DEFAULT_FILTERS, failingStorage())).toEqual(DEFAULT_FILTERS)
    expect(writeStored('jobswipe.saved.v1', [], failingStorage())).toBe(false)
    expect(writeStored('jobswipe.saved.v1', [], {})).toBe(false)
  })

  it('persists a versioned value when storage is available', () => {
    const values = new Map()
    const storage = { setItem: (key, value) => values.set(key, value) }
    expect(writeStored('jobswipe.filters.v1', { city: 'Łódź' }, storage)).toBe(true)
    expect(JSON.parse(values.get('jobswipe.filters.v1'))).toEqual({ city: 'Łódź' })
  })

  it('normalizes filter state and retains the sensible defaults', () => {
    expect(normalizeFilters({ city: 'Łódź', require_salary: false })).toEqual({
      city: 'Łódź',
      blocked_tags: ['kat_d', 'kat_c', 'prowizja_scam'],
      blocked_industries: [],
      require_salary: false,
    })
  })

  it('discards malformed saved snapshots and dismissal identifiers', () => {
    expect(normalizeSavedJobs(['bad', { hash: 'x' }, { hash: 'h', title: 'Praca', company: 'Firma', city: 'Łódź', url: 'https://example.org' }])).toHaveLength(1)
    expect(normalizeDismissedHashes(['abc', 4, null])).toEqual(['abc'])
  })
})
