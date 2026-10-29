/** Fetch JSON and surface HTTP errors consistently, including validation messages. */
export const apiRequest = async <T = any>(url: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(url, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : null
    throw new Error(detail || `Request failed (${response.status}). Please try again.`)
  }
  return response.json()
}
