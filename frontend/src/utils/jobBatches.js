export const JOB_BATCH_LIMIT = 50

export function filterJobsForCurrentExclusions(jobs, savedJobs, dismissedHashes) {
  const excluded = new Set([
    ...savedJobs.map((job) => job.hash),
    ...dismissedHashes,
  ])
  return jobs.filter((job) => !excluded.has(job.hash))
}

export function hasFullJobBatch(jobs) {
  return Array.isArray(jobs) && jobs.length >= JOB_BATCH_LIMIT
}
