export interface ApplicationAssets {
  id: string
  cover_letter_markdown: string
  resume_markdown: string
  cover_letter_pdf_path?: string
  resume_pdf_path?: string
  ans_why_company_250: string
  ans_why_company_500: string
  ans_technical_challenge_250: string
  ans_technical_challenge_500: string
  ans_python_go_proficiency_220: string
  ans_location_relocation_220: string
  custom_qa?: Record<string, string>
}
export interface HiringContacts {
  primary_email?: string
  is_direct_listing_email: boolean
  direct_emails: string[]
  derived_inboxes: string[]
  mailto_url?: string
}
export interface Job {
  id: string
  company_name: string
  job_title: string
  source: string
  source_url: string
  location_raw?: string
  description_raw?: string
  match_score: number
  match_reasoning?: string
  tech_stack_tags: string[]
  status: string
  organization_type?: string
  is_founder_led?: boolean
  created_at: string
  applied_at?: string
  assets?: ApplicationAssets
  hiring_contacts?: HiringContacts
}
export const jobTitle = (job: Job) => job.job_title?.trim() || 'Role title not provided'
export const jobLocation = (job: Job) => job.location_raw?.trim() || 'Location unspecified'
const sources: Record<string,string> = { hackernews: 'Hacker News', reddit: 'Reddit', greenhouse: 'Greenhouse', lever: 'Lever', ashby: 'Ashby', manual: 'Added manually' }
export const jobSource = (source: string) => sources[source] || source
const statuses: Record<string,string> = {ready_to_apply:'Materials ready', queued_for_llm:'Preparing materials', applied:'Applied', archived:'Ignored', new:'Not yet tailored'}
export const jobStatus = (status: string) => statuses[status] || status
export const relativeDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'
  const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000))
  return days === 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 7 ? `${days} days ago` : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
export const listingUrl = (value?: string) => value && /^https?:\/\//i.test(value) ? value : undefined
