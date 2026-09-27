<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search, ExternalLink, ArrowRight, CheckCircle, Clock,
  Filter, Sparkles, Building2, MapPin, Loader2, Zap,
  Calendar, ArrowUpDown, ChevronLeft, ChevronRight,
  ChevronsLeft, ChevronsRight, X, AlertCircle,
  EyeOff, RotateCcw, Mail, Globe, Rocket
} from 'lucide-vue-next'

interface JobAsset {
  id: string
  ans_why_company_250: string
  cover_letter_pdf_path: string
}

interface HiringContacts {
  primary_email?: string
  is_direct_listing_email: boolean
  direct_emails: string[]
  derived_inboxes: string[]
  mailto_url?: string
}

interface JobItem {
  id: string
  company_name: string
  job_title: string
  source: string
  source_url: string
  location_raw: string
  match_score: number
  match_reasoning: string
  tech_stack_tags: string[]
  status: string
  is_founder_led?: boolean
  created_at: string
  assets?: JobAsset
  hiring_contacts?: HiringContacts
}

interface JobStats {
  ready_to_apply: number
  queued_for_llm: number
  applied: number
  archived: number
  founder_led: number
  total: number
}

const props = defineProps<{
  apiBase?: string
}>()

const emit = defineEmits(['refresh', 'tailorTriggered'])

const router = useRouter()
const config = useRuntimeConfig()
const apiBase = computed(() => props.apiBase ?? config.public.apiBase ?? 'http://localhost:8000')

// State
const jobs = ref<JobItem[]>([])
const loading = ref(true)
const selectedIndex = ref(0)
const searchQuery = ref('')
const searchDebounceTimer = ref<any>(null)
const ignoringJobId = ref<string | null>(null)

type TabType = 'ready_to_apply' | 'queued_for_llm' | 'applied' | 'archived' | 'all'
const activeTab = ref<TabType>('ready_to_apply')
const sourceFilter = ref<string>('all') // all, greenhouse, lever, ashby, reddit, hackernews
const founderLedOnly = ref<boolean>(false)
const minScore = ref<number>(65)
const daysFilter = ref<number | null>(null) // null = all time, 1 = 24h, 3 = 3d, 7 = 7d, 14 = 14d, 30 = 30d
const sortBy = ref<string>('founder_first') // founder_first, score_desc, date_desc, date_asc, company_asc

// Pagination
const page = ref(1)
const limit = ref(50)
const totalItems = ref(0)
const totalPages = ref(1)

// Stats
const stats = ref<JobStats>({
  ready_to_apply: 0,
  queued_for_llm: 0,
  applied: 0,
  archived: 0,
  founder_led: 0,
  total: 0
})

// Fetch live counts
const fetchStats = async () => {
  try {
    const params = new URLSearchParams()
    if (daysFilter.value !== null) {
      params.append('days', daysFilter.value.toString())
    }
    if (sourceFilter.value && sourceFilter.value !== 'all') {
      params.append('source', sourceFilter.value)
    }
    const queryString = params.toString() ? `?${params.toString()}` : ''
    const res = await fetch(`${apiBase.value}/api/jobs/stats${queryString}`)
    if (res.ok) {
      stats.value = await res.json()
    }
  } catch (err) {
    console.error('Failed to fetch job stats:', err)
  }
}

// Fetch paginated jobs
const fetchJobs = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    const params = new URLSearchParams()
    if (activeTab.value !== 'all') {
      params.append('status', activeTab.value)
    }
    if (sourceFilter.value && sourceFilter.value !== 'all') {
      params.append('source', sourceFilter.value)
    }
    if (founderLedOnly.value) {
      params.append('founder_led_only', 'true')
    }
    if (minScore.value > 0) {
      params.append('min_score', minScore.value.toString())
    }
    if (daysFilter.value !== null) {
      params.append('days', daysFilter.value.toString())
    }
    if (sortBy.value) {
      params.append('sort_by', sortBy.value)
    }
    if (searchQuery.value.trim()) {
      params.append('search', searchQuery.value.trim())
    }
    params.append('page', page.value.toString())
    params.append('limit', limit.value.toString())
    params.append('paginate', 'true')

    const res = await fetch(`${apiBase.value}/api/jobs?${params.toString()}`)
    if (!res.ok) throw new Error(`HTTP error ${res.status}`)
    const data = await res.json()

    if (data.items) {
      jobs.value = data.items
      totalItems.value = data.total
      totalPages.value = data.total_pages || 1
      page.value = data.page || page.value
    } else if (Array.isArray(data)) {
      jobs.value = data
      totalItems.value = data.length
      totalPages.value = 1
    }
    selectedIndex.value = 0
  } catch (err) {
    console.error('Failed to fetch jobs:', err)
  } finally {
    if (!silent) loading.value = false
  }
}

const toggleFounderLedOnly = () => {
  founderLedOnly.value = !founderLedOnly.value
  page.value = 1
  fetchJobs()
}

// Date formatting helper
const formatRelativeDate = (dateStr?: string) => {
  if (!dateStr) return 'Recently'
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    if (diffMs < 0) return 'Just now'

    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSecs < 60) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`

    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return 'Recently'
  }
}

const formatFullDate = (dateStr?: string) => {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short'
    })
  } catch {
    return dateStr
  }
}

const getScoreBadgeClass = (score: number) => {
  if (score >= 85) return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
  if (score >= 70) return 'bg-blue-500/15 text-blue-400 border-blue-500/30'
  if (score >= 60) return 'bg-amber-500/15 text-amber-400 border-amber-500/30'
  return 'bg-slate-700/30 text-slate-400 border-slate-700/50'
}

const getSourceBadgeClass = (src: string) => {
  switch (src?.toLowerCase()) {
    case 'greenhouse': return 'bg-emerald-950/80 text-emerald-300 border-emerald-800/40'
    case 'lever': return 'bg-indigo-950/80 text-indigo-300 border-indigo-800/40'
    case 'ashby': return 'bg-purple-950/80 text-purple-300 border-purple-800/40'
    case 'reddit': return 'bg-orange-950/80 text-orange-300 border-orange-800/40'
    case 'hackernews': return 'bg-amber-950/80 text-amber-300 border-amber-800/40'
    default: return 'bg-slate-800 text-slate-300 border-slate-700'
  }
}

const executeJob = (jobId: string) => {
  router.push(`/execute/${jobId}`)
}

// Watchers
const switchTab = (tab: TabType) => {
  activeTab.value = tab
  // Sensible defaults per tab
  if (tab === 'ready_to_apply') {
    minScore.value = 65
    sortBy.value = 'founder_first'
  } else if (tab === 'queued_for_llm') {
    minScore.value = 0
    sortBy.value = 'date_desc'
  } else {
    minScore.value = 0
  }
  page.value = 1
  fetchJobs()
}

const handleDateChange = () => {
  page.value = 1
  fetchJobs()
  fetchStats()
}

const handleSourceChange = () => {
  page.value = 1
  fetchJobs()
  fetchStats()
}

const handleIgnoreJob = async (jobId: string) => {
  ignoringJobId.value = jobId
  try {
    const res = await fetch(`${apiBase.value}/api/jobs/${jobId}/ignore`, { method: 'POST' })
    if (res.ok) {
      jobs.value = jobs.value.filter(j => j.id !== jobId)
      totalItems.value = Math.max(0, totalItems.value - 1)
      stats.value.archived++
      if (activeTab.value === 'ready_to_apply') stats.value.ready_to_apply = Math.max(0, stats.value.ready_to_apply - 1)
      else if (activeTab.value === 'queued_for_llm') stats.value.queued_for_llm = Math.max(0, stats.value.queued_for_llm - 1)
      else if (activeTab.value === 'applied') stats.value.applied = Math.max(0, stats.value.applied - 1)
      if (jobs.value.length === 0 && page.value > 1) {
        goToPage(page.value - 1)
      }
    }
  } catch (err) {
    console.error('Failed to ignore job:', err)
  } finally {
    ignoringJobId.value = null
  }
}

const handleUnignoreJob = async (jobId: string) => {
  ignoringJobId.value = jobId
  try {
    const res = await fetch(`${apiBase.value}/api/jobs/${jobId}/unignore`, { method: 'POST' })
    if (res.ok) {
      jobs.value = jobs.value.filter(j => j.id !== jobId)
      totalItems.value = Math.max(0, totalItems.value - 1)
      stats.value.archived = Math.max(0, stats.value.archived - 1)
      fetchStats()
      if (jobs.value.length === 0 && page.value > 1) {
        goToPage(page.value - 1)
      }
    }
  } catch (err) {
    console.error('Failed to unignore job:', err)
  } finally {
    ignoringJobId.value = null
  }
}

const handleSortChange = () => {
  page.value = 1
  fetchJobs()
}

const handleScoreChange = () => {
  page.value = 1
  fetchJobs()
}

const handleLimitChange = () => {
  page.value = 1
  fetchJobs()
}

const goToPage = (p: number) => {
  if (p < 1 || p > totalPages.value || p === page.value) return
  page.value = p
  fetchJobs()
  // Scroll to top of table
  const el = document.getElementById('job-triage-table')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Debounced search
const onSearchInput = () => {
  if (searchDebounceTimer.value) clearTimeout(searchDebounceTimer.value)
  searchDebounceTimer.value = setTimeout(() => {
    page.value = 1
    fetchJobs()
  }, 300)
}

const clearSearch = () => {
  searchQuery.value = ''
  page.value = 1
  fetchJobs()
}

// Generate page pills with ellipsis
const visiblePages = computed(() => {
  const current = page.value
  const total = totalPages.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  if (current <= 4) {
    return [1, 2, 3, 4, 5, '...', total]
  }
  if (current >= total - 3) {
    return [1, '...', total - 4, total - 3, total - 2, total - 1, total]
  }
  return [1, '...', current - 1, current, current + 1, '...', total]
})

// Range string (e.g. 1 - 50 of 707)
const showingRange = computed(() => {
  if (totalItems.value === 0) return '0 opportunities'
  const start = (page.value - 1) * limit.value + 1
  const end = Math.min(page.value * limit.value, totalItems.value)
  return `${start} - ${end} of ${totalItems.value.toLocaleString()}`
})

// Keyboard shortcuts for rapid triage and pagination
const handleKeyDown = (e: KeyboardEvent) => {
  if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA' || document.activeElement?.tagName === 'SELECT') {
    return
  }

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (selectedIndex.value < jobs.value.length - 1) {
      selectedIndex.value++
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (selectedIndex.value > 0) {
      selectedIndex.value--
    }
  } else if (e.key === 'ArrowRight') {
    if (page.value < totalPages.value) {
      e.preventDefault()
      goToPage(page.value + 1)
    }
  } else if (e.key === 'ArrowLeft') {
    if (page.value > 1) {
      e.preventDefault()
      goToPage(page.value - 1)
    }
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const selected = jobs.value[selectedIndex.value]
    if (selected) {
      executeJob(selected.id)
    }
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeyDown)
  await fetchStats()
  await fetchJobs()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  if (searchDebounceTimer.value) clearTimeout(searchDebounceTimer.value)
})

defineExpose({
  fetchJobs,
  fetchStats
})
</script>

<template>
  <div id="job-triage-table" class="space-y-4">
    <!-- Controls Bar -->
    <div class="glass-panel p-4 rounded-xl flex flex-col xl:flex-row items-stretch xl:items-center justify-between gap-4">
      
      <!-- Status Tabs with live count badges -->
      <div class="flex items-center gap-1.5 p-1 rounded-lg bg-dark-900 border border-white/5 overflow-x-auto">
        <button
          @click="switchTab('ready_to_apply')"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'ready_to_apply' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <span>Ready to Apply</span>
          <span
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="activeTab === 'ready_to_apply' ? 'bg-white/20 text-white' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.ready_to_apply.toLocaleString() }}
          </span>
        </button>

        <button
          @click="switchTab('queued_for_llm')"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'queued_for_llm' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <span class="flex items-center gap-1.5">
            <span v-if="stats.queued_for_llm > 0" class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span>
            <span>Queued & Processing</span>
          </span>
          <span
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="activeTab === 'queued_for_llm' ? 'bg-white/20 text-white' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.queued_for_llm.toLocaleString() }}
          </span>
        </button>

        <button
          @click="switchTab('applied')"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'applied' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <span>Applied History</span>
          <span
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="activeTab === 'applied' ? 'bg-white/20 text-white' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.applied.toLocaleString() }}
          </span>
        </button>

        <button
          @click="switchTab('archived')"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'archived' ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <span class="flex items-center gap-1.5">
            <EyeOff class="w-3.5 h-3.5 text-slate-400" />
            <span>Ignored</span>
          </span>
          <span
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="activeTab === 'archived' ? 'bg-white/20 text-white' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.archived.toLocaleString() }}
          </span>
        </button>

        <button
          @click="switchTab('all')"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'all' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <span>All Opportunities</span>
          <span
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="activeTab === 'all' ? 'bg-white/20 text-white' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.total.toLocaleString() }}
          </span>
        </button>
      </div>

      <!-- Filters Toolbar -->
      <div class="flex flex-wrap items-center gap-2.5 w-full xl:w-auto">
        <!-- Search Field -->
        <div class="relative flex-1 sm:w-60 min-w-[180px]">
          <Search class="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            v-model="searchQuery"
            @input="onSearchInput"
            type="text"
            placeholder="Search company, title, stack..."
            class="w-full pl-8 pr-7 py-1.5 bg-dark-900 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
          />
          <button
            v-if="searchQuery"
            @click="clearSearch"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Job Source Filter -->
        <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-900 border border-white/10 text-xs">
          <Globe class="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span class="text-slate-400 hidden sm:inline">Source:</span>
          <select
            v-model="sourceFilter"
            @change="handleSourceChange"
            class="bg-transparent text-white font-medium focus:outline-none cursor-pointer pr-1 uppercase text-xs"
          >
            <option value="all" class="bg-dark-900 text-white">All Sources</option>
            <option value="hackernews" class="bg-dark-900 text-white">Hacker News</option>
            <option value="reddit" class="bg-dark-900 text-white">Reddit</option>
            <option value="greenhouse" class="bg-dark-900 text-white">Greenhouse</option>
            <option value="lever" class="bg-dark-900 text-white">Lever</option>
            <option value="ashby" class="bg-dark-900 text-white">Ashby</option>
          </select>
        </div>

        <!-- Founder-Led Only Toggle Button -->
        <button
          @click="toggleFounderLedOnly"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border shadow-sm"
          :class="founderLedOnly
            ? 'bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-300 border-amber-500/40 shadow-glow-amber'
            : 'bg-dark-900 hover:bg-dark-850 text-slate-400 hover:text-white border-white/10'"
          title="Filter specifically for founder-led and community opportunities"
        >
          <Rocket class="w-3.5 h-3.5" :class="founderLedOnly ? 'text-amber-400' : 'text-slate-500'" />
          <span class="whitespace-nowrap">Founder-Led</span>
          <span
            v-if="stats.founder_led > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold"
            :class="founderLedOnly ? 'bg-amber-400/20 text-amber-300' : 'bg-dark-800 text-slate-400'"
          >
            {{ stats.founder_led }}
          </span>
        </button>

        <!-- Date Posted Filter -->
        <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-900 border border-white/10 text-xs">
          <Calendar class="w-3.5 h-3.5 text-brand-400 shrink-0" />
          <span class="text-slate-400 hidden sm:inline">Date:</span>
          <select
            v-model="daysFilter"
            @change="handleDateChange"
            class="bg-transparent text-white font-medium focus:outline-none cursor-pointer pr-1"
          >
            <option :value="null" class="bg-dark-900 text-white">All Time</option>
            <option :value="1" class="bg-dark-900 text-white">Past 24 Hours</option>
            <option :value="3" class="bg-dark-900 text-white">Past 3 Days</option>
            <option :value="7" class="bg-dark-900 text-white">Past 7 Days</option>
            <option :value="14" class="bg-dark-900 text-white">Past 14 Days</option>
            <option :value="30" class="bg-dark-900 text-white">Past 30 Days</option>
          </select>
        </div>

        <!-- Sort By Selector -->
        <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-900 border border-white/10 text-xs">
          <ArrowUpDown class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span class="text-slate-400 hidden sm:inline">Sort:</span>
          <select
            v-model="sortBy"
            @change="handleSortChange"
            class="bg-transparent text-white font-medium focus:outline-none cursor-pointer pr-1"
          >
            <option value="founder_first" class="bg-dark-900 text-white">🚀 Founder-Led First</option>
            <option value="score_desc" class="bg-dark-900 text-white">Highest Match</option>
            <option value="date_desc" class="bg-dark-900 text-white">Newest First</option>
            <option value="date_asc" class="bg-dark-900 text-white">Oldest First</option>
            <option value="company_asc" class="bg-dark-900 text-white">Company (A-Z)</option>
          </select>
        </div>

        <!-- Min Score Selector -->
        <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-900 border border-white/10 text-xs">
          <span class="text-slate-400 whitespace-nowrap">Score:</span>
          <select
            v-model.number="minScore"
            @change="handleScoreChange"
            class="bg-transparent text-white font-mono font-semibold focus:outline-none cursor-pointer pr-1"
          >
            <option :value="0" class="bg-dark-900 text-white">Any Score</option>
            <option :value="65" class="bg-dark-900 text-white">&ge; 65%</option>
            <option :value="75" class="bg-dark-900 text-white">&ge; 75%</option>
            <option :value="85" class="bg-dark-900 text-white">&ge; 85%</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Table Container -->
    <div class="glass-panel rounded-xl overflow-hidden border border-white/10">
      <!-- Loading Spinner -->
      <div v-if="loading" class="p-16 text-center text-slate-400">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-2 border-brand-500 border-t-transparent mb-3"></div>
        <p class="text-sm font-medium">Fetching tailored opportunities...</p>
        <p class="text-xs text-slate-500 mt-1">Filtering by active parameters and calculating match vectors</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="jobs.length === 0" class="p-16 text-center text-slate-400">
        <Building2 class="w-12 h-12 mx-auto text-slate-600 mb-3" />
        <h3 class="text-base font-semibold text-slate-200">No opportunities match current filter</h3>
        <p class="text-xs text-slate-400 mt-1 max-w-md mx-auto">
          No jobs found under <span class="text-white font-medium">"{{ activeTab.replace(/_/g, ' ') }}"</span> 
          with current score (&ge; {{ minScore }}%) and date filter.
        </p>

        <div class="mt-4 flex flex-wrap items-center justify-center gap-2">
          <button
            v-if="sourceFilter !== 'all'"
            @click="sourceFilter = 'all'; handleSourceChange()"
            class="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 border border-white/10 text-xs font-semibold transition-colors"
          >
            Clear Source Filter
          </button>
          <button
            v-if="daysFilter !== null"
            @click="daysFilter = null; handleDateChange()"
            class="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 border border-white/10 text-xs font-semibold transition-colors"
          >
            Clear Date Filter
          </button>
          <button
            v-if="minScore > 0"
            @click="minScore = 0; handleScoreChange()"
            class="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 border border-white/10 text-xs font-semibold transition-colors"
          >
            Clear Min Score
          </button>
          <button
            v-if="activeTab !== 'ready_to_apply' && stats.ready_to_apply > 0"
            @click="switchTab('ready_to_apply')"
            class="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-colors"
          >
            View Ready to Apply ({{ stats.ready_to_apply.toLocaleString() }})
          </button>
          <button
            v-if="activeTab !== 'all'"
            @click="switchTab('all')"
            class="px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 border border-white/10 text-xs font-semibold transition-colors"
          >
            Show All Opportunities ({{ stats.total.toLocaleString() }})
          </button>
        </div>
      </div>

      <!-- Main Table -->
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b border-white/10 bg-dark-900/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <th class="py-3 px-4 w-28">Match</th>
              <th class="py-3 px-4">Company & Role</th>
              <th class="py-3 px-4 w-28">Source</th>
              <th class="py-3 px-4">Tech Stack Alignment</th>
              <th class="py-3 px-4 w-36 text-right">Action</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5 text-xs">
            <tr
              v-for="(job, index) in jobs"
              :key="job.id"
              @click="selectedIndex = index"
              @dblclick="executeJob(job.id)"
              class="group hover:bg-white/[0.04] transition-colors cursor-pointer"
              :class="{
                'bg-brand-500/[0.08] border-l-2 border-brand-500': selectedIndex === index
              }"
            >
              <!-- Match Score Badge -->
              <td class="py-3.5 px-4">
                <div class="flex items-center gap-1.5">
                  <div
                    v-if="job.status === 'queued_for_llm'"
                    class="flex items-center gap-1.5 py-1 px-2.5 rounded-md bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 font-mono text-[11px]"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
                    <span>Queued</span>
                  </div>
                  <span
                    v-else
                    class="font-mono font-bold text-xs px-2.5 py-1 rounded-md border"
                    :class="getScoreBadgeClass(job.match_score)"
                  >
                    {{ job.match_score }}%
                  </span>
                </div>
              </td>

              <!-- Company & Role -->
              <td class="py-3.5 px-4">
                <div>
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-white text-sm group-hover:text-brand-400 transition-colors">
                      {{ job.company_name }}
                    </span>

                    <!-- Founder-Led Badge -->
                    <span
                      v-if="job.is_founder_led"
                      class="px-1.5 py-0.5 rounded text-[10px] bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 font-semibold shadow-sm"
                      title="Direct founder or founding engineering team opportunity"
                    >
                      <Rocket class="w-3 h-3 text-amber-400" />
                      Founder-Led
                    </span>

                    <span v-if="job.status === 'applied'" class="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      Applied
                    </span>
                    <span v-else-if="job.status === 'archived'" class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-white/10">
                      Ignored
                    </span>
                    <span v-else-if="job.status === 'queued_for_llm'" class="px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                      Tailoring
                    </span>

                    <!-- Direct Hiring Email Badge -->
                    <span
                      v-if="job.hiring_contacts?.is_direct_listing_email"
                      class="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 font-mono font-medium"
                      :title="`Direct hiring email in listing: ${job.hiring_contacts.primary_email}`"
                    >
                      <Mail class="w-3 h-3 text-emerald-400" />
                      Direct Email
                    </span>
                  </div>
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-0.5 text-slate-300">
                    <span class="font-medium text-slate-200">{{ job.job_title }}</span>
                    <span class="text-slate-500 text-[11px] flex items-center gap-1">
                      <MapPin class="w-3 h-3 text-slate-500" />
                      {{ job.location_raw || 'Remote' }}
                    </span>
                    <!-- Date Posted Pill -->
                    <span
                      class="text-slate-500 text-[11px] flex items-center gap-1 font-mono"
                      :title="formatFullDate(job.created_at)"
                    >
                      <Clock class="w-3 h-3 text-slate-500" />
                      {{ formatRelativeDate(job.created_at) }}
                    </span>
                  </div>
                  <p v-if="job.match_reasoning" class="text-[11px] text-slate-400 mt-1 line-clamp-1 italic">
                    &ldquo;{{ job.match_reasoning }}&rdquo;
                  </p>
                </div>
              </td>

              <!-- Source ATS -->
              <td class="py-3.5 px-4">
                <span
                  class="font-mono text-[10px] uppercase font-semibold px-2 py-0.5 rounded border tracking-wide"
                  :class="getSourceBadgeClass(job.source)"
                >
                  {{ job.source }}
                </span>
              </td>

              <!-- Tech Stack Tags -->
              <td class="py-3.5 px-4">
                <div class="flex flex-wrap gap-1.5 max-w-md">
                  <span
                    v-for="tag in job.tech_stack_tags?.slice(0, 5)"
                    :key="tag"
                    class="px-2 py-0.5 rounded bg-dark-850 text-slate-300 border border-white/5 text-[11px] font-mono"
                  >
                    {{ tag }}
                  </span>
                  <span
                    v-if="job.tech_stack_tags?.length > 5"
                    class="text-slate-500 text-[10px] self-center font-mono"
                  >
                    +{{ job.tech_stack_tags.length - 5 }}
                  </span>
                </div>
              </td>

              <!-- Execute & Ignore Action Buttons -->
              <td class="py-3.5 px-4 text-right">
                <div class="flex items-center justify-end gap-1.5">
                  <!-- If Archived / Ignored, show Restore button -->
                  <button
                    v-if="job.status === 'archived'"
                    @click.stop="handleUnignoreJob(job.id)"
                    :disabled="ignoringJobId === job.id"
                    class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-dark-850 hover:bg-dark-800 text-slate-300 hover:text-white border border-white/10 transition-all"
                    title="Restore to Active Queue"
                  >
                    <RotateCcw class="w-3.5 h-3.5 text-brand-400" :class="{ 'animate-spin': ignoringJobId === job.id }" />
                    <span>Restore</span>
                  </button>

                  <template v-else>
                    <!-- Quick Ignore Button -->
                    <button
                      @click.stop="handleIgnoreJob(job.id)"
                      :disabled="ignoringJobId === job.id"
                      class="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all"
                      title="Ignore listing (hide from active queue)"
                    >
                      <EyeOff class="w-3.5 h-3.5" :class="{ 'opacity-30': ignoringJobId === job.id }" />
                    </button>

                    <!-- Main Action -->
                    <button
                      @click.stop="executeJob(job.id)"
                      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all group-hover:scale-105"
                      :class="job.status === 'applied' 
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' 
                        : job.status === 'queued_for_llm'
                          ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                          : 'bg-brand-600 hover:bg-brand-500 text-white shadow-glow-blue'"
                    >
                      <span>{{ job.status === 'applied' ? 'Review' : (job.status === 'queued_for_llm' ? 'Tailor' : 'Execute') }}</span>
                      <ArrowRight class="w-3.5 h-3.5" />
                    </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination & Navigation Footer -->
      <div class="px-4 py-3 bg-dark-900/90 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
        <!-- Range & Page Size -->
        <div class="flex items-center gap-4">
          <span>Showing <strong class="text-white">{{ showingRange }}</strong></span>
          
          <div class="flex items-center gap-1.5 pl-3 border-l border-white/10">
            <span class="text-slate-500 text-[11px]">Per page:</span>
            <select
              v-model.number="limit"
              @change="handleLimitChange"
              class="bg-dark-850 border border-white/10 rounded px-2 py-0.5 text-xs text-white focus:outline-none cursor-pointer"
            >
              <option :value="25">25</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </div>
        </div>

        <!-- Page Buttons -->
        <div v-if="totalPages > 1" class="flex items-center gap-1">
          <!-- First Page -->
          <button
            @click="goToPage(1)"
            :disabled="page <= 1"
            class="p-1.5 rounded-md hover:bg-dark-850 text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
            title="First Page"
          >
            <ChevronsLeft class="w-3.5 h-3.5" />
          </button>

          <!-- Prev Page -->
          <button
            @click="goToPage(page - 1)"
            :disabled="page <= 1"
            class="p-1.5 rounded-md hover:bg-dark-850 text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
            title="Previous Page (Left Arrow)"
          >
            <ChevronLeft class="w-3.5 h-3.5" />
          </button>

          <!-- Page Numbers -->
          <div class="flex items-center gap-1 px-1">
            <template v-for="(p, i) in visiblePages" :key="i">
              <span v-if="p === '...'" class="px-1 text-slate-600 font-mono">...</span>
              <button
                v-else
                @click="goToPage(Number(p))"
                class="min-w-[28px] h-7 px-2 rounded-md font-mono text-xs font-semibold transition-all"
                :class="page === p 
                  ? 'bg-brand-600 text-white shadow-sm' 
                  : 'bg-dark-850/60 hover:bg-dark-800 text-slate-300 hover:text-white border border-white/5'"
              >
                {{ p }}
              </button>
            </template>
          </div>

          <!-- Next Page -->
          <button
            @click="goToPage(page + 1)"
            :disabled="page >= totalPages"
            class="p-1.5 rounded-md hover:bg-dark-850 text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
            title="Next Page (Right Arrow)"
          >
            <ChevronRight class="w-3.5 h-3.5" />
          </button>

          <!-- Last Page -->
          <button
            @click="goToPage(totalPages)"
            :disabled="page >= totalPages"
            class="p-1.5 rounded-md hover:bg-dark-850 text-slate-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
            title="Last Page"
          >
            <ChevronsRight class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Keyboard Hint -->
        <div class="hidden lg:flex items-center gap-2 text-[11px] text-slate-500">
          <span><kbd class="px-1 py-0.5 rounded bg-dark-800 border border-white/10 text-slate-300 font-mono">&larr;</kbd> <kbd class="px-1 py-0.5 rounded bg-dark-800 border border-white/10 text-slate-300 font-mono">&rarr;</kbd> pages</span>
          <span><kbd class="px-1 py-0.5 rounded bg-dark-800 border border-white/10 text-slate-300 font-mono">&uarr;</kbd> <kbd class="px-1 py-0.5 rounded bg-dark-800 border border-white/10 text-slate-300 font-mono">&darr;</kbd> rows</span>
          <span><kbd class="px-1 py-0.5 rounded bg-dark-800 border border-white/10 text-slate-300 font-mono">Enter</kbd> execute</span>
        </div>
      </div>
    </div>
  </div>
</template>
