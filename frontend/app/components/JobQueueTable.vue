<script setup lang="ts">
import { Search, SlidersHorizontal, LayoutGrid, AlignJustify, MapPin, ChevronLeft, ChevronRight, RefreshCw, X, ArrowLeft, ArrowRight, EyeOff, RotateCcw } from 'lucide-vue-next'
import { jobTitle, jobLocation, relativeDate, jobSource } from '~/types/jobs'
import type { Job } from '~/types/jobs'
const props = defineProps<{ applied?: boolean }>()
const route = useRoute(), router = useRouter()
const { apiBase, queueRevision, counts, jobsChanged } = useWorkspace()
const jobs = ref<Job[]>([]), loading = ref(true), error = ref(''), actionError = ref('')
const total = ref(0), totalPages = ref(1), selectedId = ref(''), mobileDetail = ref(false)
const compact = ref(false), showFilters = ref(false), busy = ref(false), undoJob = ref<Job | null>(null)
type BulkAction = 'ignore' | 'restore' | 'prepare' | 'mark_applied'
const checkedIds = ref<string[]>([]), bulkMessage = ref('')
const bulkSkipped = ref<{id:string, reason:string}[]>([])
const undoBatch = ref<Record<string,string> | null>(null)
const bulkDialog = ref<HTMLDialogElement | null>(null)
const pendingAction = ref<BulkAction>('ignore')
const allChecked = computed(() => jobs.value.length > 0 && jobs.value.every(job => checkedIds.value.includes(job.id)))
const toggleChecked = (id:string) => { checkedIds.value = checkedIds.value.includes(id) ? checkedIds.value.filter(value => value !== id) : [...checkedIds.value,id] }
const eligibleCount = (action:BulkAction) => jobs.value.filter(job => checkedIds.value.includes(job.id) && (action === 'prepare' ? job.status === 'new' : action === 'mark_applied' ? job.status === 'ready_to_apply' : ['new','ready_to_apply'].includes(job.status))).length
const askBulk = (action:BulkAction) => { pendingAction.value = action; bulkDialog.value?.showModal() }
const runBulk = async (action:BulkAction) => {
  if (busy.value) return
  busy.value = true; actionError.value = ''; bulkMessage.value = ''; bulkSkipped.value = []
  const ids = action === 'restore' ? Object.keys(undoBatch.value || {}) : [...checkedIds.value]
  try {
    const result = await apiRequest<{updated_ids:string[], skipped:{id:string,reason:string}[], previous_statuses:Record<string,string>}>(`${apiBase}/api/jobs/bulk`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action,job_ids:ids,previous_statuses:action === 'restore' ? undoBatch.value : {}})
    })
    bulkDialog.value?.close()
    bulkSkipped.value = result.skipped
    const verb = {ignore:'ignored',restore:'restored',prepare:'queued for preparation',mark_applied:'marked applied'}[action]
    bulkMessage.value = `${result.updated_ids.length} jobs ${verb}.${result.skipped.length ? ` ${result.skipped.length} skipped.` : ''}`
    if (action === 'ignore') undoBatch.value = Object.keys(result.previous_statuses).length ? result.previous_statuses : null
    if (action === 'restore') undoBatch.value = null
    checkedIds.value = []; jobsChanged(); await fetchJobs()
  } catch (err:any) { actionError.value = err.message || 'Could not update selected jobs.' }
  finally { busy.value = false }
}
const search = ref(typeof route.query.search === 'string' ? route.query.search : '')
const query = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const status = computed(() => props.applied ? 'applied' : ['ready_to_apply','queued_for_llm','all','archived','new'].includes(query('status')) ? query('status') : 'ready_to_apply')
const page = computed(() => Math.max(1, Number(query('page')) || 1))
const limit = computed(() => [25,50,100].includes(Number(query('limit'))) ? Number(query('limit')) : 50)
const score = computed(() => Math.max(0, Math.min(100, Number(query('min_score', status.value === 'ready_to_apply' ? '65' : '0')) || 0)))
const selected = computed(() => jobs.value.find(job => job.id === selectedId.value) || jobs.value[0])
const filtersActive = computed(() => query('organization_type') || query('source') || query('days') || query('founder_led_only') === 'true' || score.value > 0)
const params = computed(() => {
  const params = new URLSearchParams({ page: String(page.value), limit: String(limit.value), paginate: 'true', sort_by: query('sort_by','score_desc'), min_score: String(score.value) })
  if (status.value !== 'all') params.set('status', status.value)
  for (const key of ['source','days','search','founder_led_only','organization_type']) if (query(key)) params.set(key, query(key))
  return params.toString()
})
const tabs = [{ value: 'ready_to_apply', label: 'Ready to apply' }, { value: 'queued_for_llm', label: 'Preparing' }, { value: 'new', label: 'Saved for later' }, { value: 'all', label: 'All roles' }, { value: 'archived', label: 'Ignored' }]
const countFor = (value: string) => counts.value ? (value === 'all' ? counts.value.total : counts.value[value])?.toLocaleString() : null
const setQuery = (patch: Record<string, string | undefined>, resetPage = true) => router.replace({ query: { ...route.query, ...(resetPage ? { page: undefined, selected: undefined } : {}), ...patch } })
let controller: AbortController | undefined, searchTimer: ReturnType<typeof setTimeout>
const fetchJobs = async () => {
  controller?.abort(); const request = new AbortController(); controller = request
  loading.value = true; error.value = ''
  try {
    const data = await apiRequest<{ items: Job[], total: number, total_pages: number }>(`${apiBase}/api/jobs?${params.value}`, { signal: request.signal })
    if (request.signal.aborted) return
    checkedIds.value = checkedIds.value.filter(id => data.items.some(job => job.id === id));
    jobs.value = data.items; total.value = data.total; totalPages.value = data.total_pages || 1
    selectedId.value = data.items.find(job => job.id === query('selected'))?.id || data.items.find(job => job.id === selectedId.value)?.id || data.items[0]?.id || ''
    if (!data.items.length && page.value > 1 && page.value > totalPages.value) await setQuery({page:String(totalPages.value)},false)
  } catch (err: any) { if (err.name !== 'AbortError') error.value = err.message || 'Could not load opportunities.' }
  finally { if (controller === request) loading.value = false }
}
const selectJob = (job: Job, openMobile = true) => { selectedId.value = job.id; mobileDetail.value = openMobile; setQuery({selected:job.id},false) }
const switchTab = (value: string) => { mobileDetail.value = false; setQuery({ status: value, min_score: value === 'ready_to_apply' ? '65' : '0' }) }
const updateSearch = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => setQuery({ search: search.value.trim() || undefined }),300) }
const prepareLocation = computed(() => selected.value ? { path: `/execute/${selected.value.id}`, query: { ...route.query, status: status.value, min_score: String(score.value), selected: selected.value.id, from: props.applied ? 'applications' : undefined } } : '/')
const updateJob = async (restore = false, undo = false) => {
  const job = undo ? undoJob.value : selected.value
  if (!job || busy.value) return
  busy.value = true; actionError.value = ''
  try {
    await apiRequest(`${apiBase}/api/jobs/${job.id}/${undo ? 'status' : restore ? 'unignore' : 'ignore'}`, {
      method:'POST', headers:{'Content-Type':'application/json'}, ...(undo ? {body:JSON.stringify({status:job.status})} : {})
    })
    undoJob.value = undo || restore ? null : {...job}
    jobsChanged(); await fetchJobs()
  } catch (err: any) { actionError.value = err.message || 'Could not update this job.' }
  finally { busy.value = false }
}
const keydown = (event: KeyboardEvent) => {
  if (document.querySelector('dialog[open]') || (event.target as HTMLElement)?.closest('input,textarea,select,[contenteditable=true]')) return
  if (event.key === '/') { event.preventDefault(); document.getElementById('job-search')?.focus() }
  if (event.key === 'Escape') mobileDetail.value = false
  if (['ArrowDown','ArrowUp'].includes(event.key)) {
    if ((event.target as HTMLElement)?.closest('a') || loading.value) return
    const index = jobs.value.findIndex(job => job.id === selected.value?.id)
    const next = jobs.value[Math.max(0,Math.min(jobs.value.length-1,index+(event.key === 'ArrowDown' ? 1 : -1)))]
    if (next) { event.preventDefault(); selectJob(next,false); document.getElementById(`job-${next.id}`)?.scrollIntoView({block:'nearest'}) }
  }
}
watch(params,() => { checkedIds.value = []; fetchJobs() })
watch(queueRevision,fetchJobs)
watch(() => route.query.search, value => { search.value = typeof value === 'string' ? value : '' })
watch(() => route.query.selected, value => { if (typeof value === 'string' && jobs.value.some(job => job.id === value)) selectedId.value = value })
onMounted(() => { fetchJobs(); window.addEventListener('keydown',keydown) })
onUnmounted(() => { controller?.abort(); clearTimeout(searchTimer); window.removeEventListener('keydown',keydown) })
</script>
<template>
  <section class="queue-view" :class="{ 'detail-open': mobileDetail, 'table-density': compact }" :aria-label="applied ? 'Applications' : 'Opportunities'">
    <div class="page-heading"><div class="heading-copy"><h1>{{ applied ? 'Applications' : 'Opportunities' }}</h1><span class="count">{{ total.toLocaleString() }} {{ applied ? 'applied' : 'roles' }}</span></div><div class="heading-actions"><button class="icon-button" :disabled="loading" aria-label="Refresh jobs" @click="fetchJobs"><RefreshCw :class="{ 'animate-spin': loading }" /></button><div class="view-toggle" role="group" aria-label="List density"><button :class="{active:!compact}" :aria-pressed="!compact" aria-label="Comfortable list" @click="compact=false"><LayoutGrid /></button><button :class="{active:compact}" :aria-pressed="compact" aria-label="Compact list" @click="compact=true"><AlignJustify /></button></div></div></div>
    <div class="controls"><nav v-if="!applied" class="tabs" aria-label="Job status"><button v-for="tab in tabs" :key="tab.value" :class="{active:status===tab.value}" :aria-pressed="status===tab.value" @click="switchTab(tab.value)">{{ tab.label }}<span class="tabcount">{{ countFor(tab.value) }}</span></button></nav><p v-else class="applications-intro">Your submitted applications and the materials you prepared.</p>
      <div class="filter-row"><label class="search"><Search aria-hidden="true" /><input id="job-search" v-model="search" type="search" placeholder="Search roles, companies or locations" aria-label="Search jobs" @input="updateSearch"><span class="shortcut desktop-only">/</span></label>
        <select class="filter" aria-label="Job source" :value="query('source')" @change="setQuery({source:($event.target as HTMLSelectElement).value || undefined})"><option value="">All sources</option><option value="hackernews">Hacker News</option><option value="reddit">Reddit</option><option value="greenhouse">Greenhouse</option><option value="lever">Lever</option><option value="ashby">Ashby</option><option value="manual">Added manually</option></select>
        <select class="filter organization-filter" aria-label="Organization type" :value="query('organization_type')" @change="setQuery({organization_type:($event.target as HTMLSelectElement).value || undefined})"><option value="">All organizations</option><option value="nonprofit">Likely NGO / nonprofit</option><option value="unknown">Organization type unknown</option></select>
        <button class="filter" :aria-pressed="query('founder_led_only')==='true'" @click="setQuery({founder_led_only:query('founder_led_only')==='true' ? undefined : 'true'})">Founder-led</button>
        <button class="filter" :aria-expanded="showFilters" aria-controls="advanced-filters" @click="showFilters=!showFilters"><SlidersHorizontal aria-hidden="true" />Filters<span v-if="filtersActive" class="filter-dot" aria-label="Filters active" /></button>
        <label class="sort">Sort by<select aria-label="Sort jobs" :value="query('sort_by','score_desc')" @change="setQuery({sort_by:($event.target as HTMLSelectElement).value})"><option value="score_desc">Best match</option><option value="founder_first">Founder-led first</option><option value="date_desc">Newest first</option><option value="date_asc">Oldest first</option><option value="company_asc">Company name</option></select></label>

      </div>
      <div v-if="showFilters" id="advanced-filters" class="advanced-filters"><label>Minimum fit<select :value="score" @change="setQuery({min_score:($event.target as HTMLSelectElement).value})"><option value="0">Any score</option><option v-for="n in [65,75,85]" :key="n" :value="n">{{ n }} or higher</option><option v-if="![0,65,75,85].includes(score)" :value="score">{{ score }} or higher</option></select></label><label>Date added<select :value="query('days')" @change="setQuery({days:($event.target as HTMLSelectElement).value || undefined})"><option value="">Any time</option><option v-for="n in [1,3,7,14,30]" :key="n" :value="n">Last {{ n }} {{ n===1 ? 'day' : 'days' }}</option></select></label><button class="text-link" @click="search='';setQuery({search:undefined,source:undefined,days:undefined,min_score:'0',founder_led_only:undefined,organization_type:undefined})">Clear filters</button></div>
    </div>
    <p v-if="query('organization_type') === 'nonprofit'" class="classification-note">Matches NGO, charity, or nonprofit terms in the company name or listing. Confirm the organization’s status before applying.</p>
    <div v-if="bulkMessage" role="status" class="workspace-notice"><span>{{ bulkMessage }}</span><button v-if="undoBatch" :disabled="busy" @click="runBulk('restore')">Undo ignore</button><button class="icon-button" aria-label="Dismiss bulk result" @click="bulkMessage='';bulkSkipped=[]"><X /></button></div>
    <details v-if="bulkSkipped.length" class="bulk-skipped"><summary>Why {{ bulkSkipped.length }} jobs were skipped</summary><ul><li v-for="item in bulkSkipped" :key="item.id">{{ jobs.find(job=>job.id===item.id)?.company_name || item.id }}: {{ item.reason }}</li></ul></details>
    <div v-if="actionError" role="alert" class="feedback-error">{{ actionError }}</div>
    <div v-if="undoJob" role="status" class="workspace-notice"><span>Ignored {{ undoJob.company_name }}.</span><button :disabled="busy" @click="updateJob(false,true)">Undo</button><button class="icon-button" aria-label="Dismiss undo" @click="undoJob=null"><X /></button></div>
    <div class="split"><section class="queue" aria-label="Job list"><div class="list-meta"><span>{{ loading ? 'Loading opportunities…' : `${total.toLocaleString()} matching ${applied ? 'applications' : 'opportunities'}` }}</span><label class="select-page"><input type="checkbox" :checked="allChecked" :indeterminate="checkedIds.length>0 && !allChecked" :disabled="loading || busy || !jobs.length" @change="checkedIds=allChecked ? [] : jobs.map(job=>job.id)">Select this page</label></div>
      <div v-if="checkedIds.length" class="bulk-toolbar" aria-label="Selected job actions"><strong>{{ checkedIds.length }} selected</strong><button class="subtle" :disabled="busy || !eligibleCount('ignore')" @click="askBulk('ignore')">Ignore ({{ eligibleCount('ignore') }})</button><button class="subtle" :disabled="busy || !eligibleCount('prepare')" @click="askBulk('prepare')">Prepare ({{ eligibleCount('prepare') }})</button><button class="secondary" :disabled="busy || !eligibleCount('mark_applied')" @click="askBulk('mark_applied')">Mark applied ({{ eligibleCount('mark_applied') }})</button><button class="icon-button" :disabled="busy" aria-label="Clear selection" @click="checkedIds=[]"><X /></button></div>
      <div v-if="loading" class="empty" role="status">Loading your opportunities…</div>
      <div v-else-if="error" class="empty" role="alert"><h2>Could not load jobs</h2><p>{{ error }}</p><button class="secondary" @click="fetchJobs">Retry</button></div>
      <div v-else-if="!jobs.length" class="empty"><h2>No matching {{ applied ? 'applications' : 'opportunities' }}</h2><p>{{ applied ? 'Submitted applications will appear here. Try clearing filters if you have already applied.' : 'Try a different search or clear the filters.' }}</p><button class="text-link" @click="search='';setQuery({search:undefined,source:undefined,days:undefined,min_score:'0',founder_led_only:undefined,organization_type:undefined})">Clear filters</button></div>
      <div v-else class="jobs"><div v-for="job in jobs" :key="job.id" class="job-select-row" :class="{checked:checkedIds.includes(job.id)}"><label class="job-checkbox"><input type="checkbox" :checked="checkedIds.includes(job.id)" :disabled="busy" :aria-label="`Select ${jobTitle(job)} at ${job.company_name}`" @change="toggleChecked(job.id)"></label><button :id="`job-${job.id}`" class="job" :class="{selected:selected?.id===job.id}" :aria-pressed="selected?.id===job.id" @click="selectJob(job)"><div class="job-top"><div><span class="job-title">{{ jobTitle(job) }}</span><div class="job-company">{{ job.company_name || 'Company unspecified' }}</div></div><span class="score">{{ job.match_score || '—' }}<small>{{ job.match_score ? 'fit' : 'pending' }}</small></span></div><div class="job-meta"><span><MapPin aria-hidden="true" />{{ jobLocation(job) }}</span><span>{{ relativeDate(applied && job.applied_at ? job.applied_at : job.created_at) }}</span></div><div class="job-tags"><span v-for="tag in job.tech_stack_tags?.slice(0,3)" :key="tag">{{ tag }}</span><span v-if="!job.tech_stack_tags?.length">{{ jobSource(job.source) }}</span><span v-if="job.organization_type==='nonprofit'">Likely nonprofit</span></div></button></div></div>
      <div class="queue-footer"><span>{{ total ? `${(page-1)*limit+1}–${Math.min(page*limit,total)} of ${total.toLocaleString()}` : '0 roles' }}</span><div class="pagination"><select aria-label="Jobs per page" :value="limit" @change="setQuery({limit:($event.target as HTMLSelectElement).value})"><option v-for="n in [25,50,100]" :key="n" :value="n">{{ n }} / page</option></select><button :disabled="page<=1 || loading" aria-label="Previous page" @click="setQuery({page:String(page-1),selected:undefined},false)"><ChevronLeft /></button><span>{{ page }} / {{ totalPages }}</span><button :disabled="page>=totalPages || loading" aria-label="Next page" @click="setQuery({page:String(page+1),selected:undefined},false)"><ChevronRight /></button></div></div>
    </section>
    <section class="preview-pane" aria-label="Selected job"><button class="mobile-back" @click="mobileDetail=false"><ArrowLeft aria-hidden="true" />{{ applied ? 'All applications' : 'All opportunities' }}</button><div v-if="selected && !loading && !error" class="detail-scroll" tabindex="0"><JobPreview :job="selected" /></div><div v-else class="empty">Select an opportunity to review the role and your fit.</div><div v-if="selected && !loading && !error" class="detail-footer"><button class="subtle" :disabled="busy" @click="updateJob(selected.status==='archived')"><component :is="selected.status==='archived' ? RotateCcw : EyeOff" aria-hidden="true" />{{ selected.status==='archived' ? 'Restore' : 'Ignore' }}</button><NuxtLink :to="prepareLocation" class="primary button-link">{{ selected.status==='applied' ? 'Review application' : 'Prepare application' }}<ArrowRight aria-hidden="true" /></NuxtLink></div></section></div>
    <dialog ref="bulkDialog" class="bulk-dialog" aria-labelledby="bulk-title" aria-describedby="bulk-description" @cancel="busy && $event.preventDefault()">
      <h2 id="bulk-title">{{ pendingAction==='ignore' ? 'Ignore selected jobs?' : pendingAction==='prepare' ? 'Prepare application materials?' : 'Mark selected jobs applied?' }}</h2>
      <p id="bulk-description">{{ eligibleCount(pendingAction) }} of {{ checkedIds.length }} selected jobs are eligible. {{ pendingAction==='mark_applied' ? 'Confirm you have already submitted these applications on the employers’ sites. This only updates your tracker.' : pendingAction==='prepare' ? 'A fit assessment, resume, cover letter, and answers will be prepared in the background. This uses your configured AI provider.' : 'They will move to Ignored. You can undo this batch after it finishes.' }}</p>
      <p v-if="actionError" role="alert" class="feedback-error">{{ actionError }}</p>
      <div class="dialog-footer"><button class="secondary" :disabled="busy" @click="bulkDialog?.close()">Cancel</button><button class="primary" :disabled="busy || !eligibleCount(pendingAction)" @click="runBulk(pendingAction)">{{ busy ? 'Updating…' : pendingAction==='ignore' ? 'Ignore jobs' : pendingAction==='prepare' ? 'Prepare materials' : 'Confirm already applied' }}</button></div>
    </dialog>
  </section>
</template>
