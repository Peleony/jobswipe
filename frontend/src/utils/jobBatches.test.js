import { describe, expect, it } from 'vitest'
import { filterJobsForCurrentExclusions, hasFullJobBatch, JOB_BATCH_LIMIT } from './jobBatches'

describe('job batches', () => {
  it('filters jobs saved or dismissed while a request was in flight', () => {
    const jobs = [{ hash: 'saved' }, { hash: 'dismissed' }, { hash: 'available' }]
    const result = filterJobsForCurrentExclusions(jobs, [{ hash: 'saved' }], ['dismissed'])
    expect(result).toEqual([{ hash: 'available' }])
  })

  it('recognizes full batches and handles empty or invalid results', () => {
    expect(hasFullJobBatch([])).toBe(false)
    expect(hasFullJobBatch(Array.from({ length: JOB_BATCH_LIMIT - 1 }))).toBe(false)
    expect(hasFullJobBatch(Array.from({ length: JOB_BATCH_LIMIT }))).toBe(true)
    expect(hasFullJobBatch(null)).toBe(false)
  })
})
