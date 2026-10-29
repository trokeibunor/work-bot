export const useWorkspace = () => {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase as string
  const showIngest = useState('ingest-open', () => false)
  const queueRevision = useState('queue-revision', () => 0)
  const metrics = useState<any>('daily-metrics', () => null)
  const counts = useState<any>('job-counts', () => null)
  const metricsError = useState('metrics-error', () => '')
  const notice = useState('workspace-notice', () => '')
  const refreshMetrics = async () => {
    const results = await Promise.allSettled([
      apiRequest(`${apiBase}/api/metrics/daily`), apiRequest(`${apiBase}/api/jobs/stats`)
    ])
    if (results[0].status === 'fulfilled') metrics.value = results[0].value
    if (results[1].status === 'fulfilled') counts.value = results[1].value
    metricsError.value = results.some(result => result.status === 'rejected') ? 'Progress could not be updated.' : ''
  }
  const jobsChanged = () => { queueRevision.value++; refreshMetrics() }
  return { apiBase, showIngest, queueRevision, metrics, counts, metricsError, notice, refreshMetrics, jobsChanged }
}
