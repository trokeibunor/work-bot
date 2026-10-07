<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  X, UploadCloud, Link2, FileText, Sparkles, CheckCircle2,
  AlertCircle, Loader2, ArrowRight, FileSpreadsheet, Trash2,
  ExternalLink, Check, Copy, ChevronRight
} from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  apiBase: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'ingested', count: number): void
}>()

type ActiveTab = 'file' | 'urls' | 'text'
const activeTab = ref<ActiveTab>('file')

// Options
const bypassFilter = ref(true)
const tailorNow = ref(true)

// File Upload State
const selectedFile = ref<File | null>(null)
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// URLs State
const urlsInput = ref('')

// Text Paste State
const textInput = ref('')
const overrideTitle = ref('')
const overrideCompany = ref('')
const overrideLocation = ref('')

// Loading & Execution State
const isSubmitting = ref(false)
const progressStatus = ref('')
const errorMessage = ref('')

// Result State
interface IngestResultItem {
  id?: string
  job_title: string
  company_name: string
  source_url: string
  status: string
  match_score?: number
  action_taken: string
  error_message?: string
}

interface IngestResponseData {
  total_received: number
  total_processed: number
  total_queued: number
  total_duplicates: number
  total_rejected: number
  results: IngestResultItem[]
}

const ingestResults = ref<IngestResponseData | null>(null)

// File drag & drop handlers
const onDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

const onDragLeave = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
}

const onDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    handleFileSelect(e.dataTransfer.files[0])
  }
}

const onFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFileSelect(target.files[0])
  }
}

const handleFileSelect = (file: File) => {
  errorMessage.value = ''
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !['pdf', 'csv', 'xlsx', 'xls'].includes(ext)) {
    errorMessage.value = `Unsupported file format ".${ext}". Please upload a .pdf, .csv, or .xlsx file.`
    return
  }
  if (file.size > 15 * 1024 * 1024) {
    errorMessage.value = 'File size exceeds 15MB limit.'
    return
  }
  selectedFile.value = file
}

const clearSelectedFile = () => {
  selectedFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// Submissions
const handleSubmit = async () => {
  errorMessage.value = ''
  isSubmitting.value = true
  ingestResults.value = null

  try {
    if (activeTab.value === 'file') {
      if (!selectedFile.value) {
        errorMessage.value = 'Please select a file to upload.'
        isSubmitting.value = false
        return
      }
      progressStatus.value = `Uploading and parsing ${selectedFile.value.name}...`
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      formData.append('bypass_filter', String(bypassFilter.value))
      formData.append('tailor_now', String(tailorNow.value))

      const res = await fetch(`${props.apiBase}/api/jobs/ingest/file`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to ingest file.')
      }
      ingestResults.value = data
      emit('ingested', data.total_processed)

    } else if (activeTab.value === 'urls') {
      const urlList = urlsInput.value
        .split('\n')
        .map(u => u.trim())
        .filter(u => u.length > 0 && (u.startsWith('http://') || u.startsWith('https://')))

      if (urlList.length === 0) {
        errorMessage.value = 'Please provide at least one valid HTTP or HTTPS job URL.'
        isSubmitting.value = false
        return
      }

      progressStatus.value = `Scraping ${urlList.length} link${urlList.length > 1 ? 's' : ''}...`
      const res = await fetch(`${props.apiBase}/api/jobs/ingest/urls`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          urls: urlList,
          bypass_filter: bypassFilter.value,
          tailor_now: tailorNow.value
        })
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to scrape URLs.')
      }
      ingestResults.value = data
      emit('ingested', data.total_processed)

    } else if (activeTab.value === 'text') {
      if (!textInput.value.trim() || textInput.value.trim().length < 20) {
        errorMessage.value = 'Please paste a job description (at least 20 characters).'
        isSubmitting.value = false
        return
      }

      progressStatus.value = 'Analyzing job description and extracting role context...'
      const res = await fetch(`${props.apiBase}/api/jobs/ingest/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textInput.value.trim(),
          job_title: overrideTitle.value.trim() || null,
          company_name: overrideCompany.value.trim() || null,
          location_raw: overrideLocation.value.trim() || null,
          bypass_filter: bypassFilter.value,
          tailor_now: tailorNow.value
        })
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to ingest job text.')
      }
      ingestResults.value = data
      emit('ingested', data.total_processed)
    }
  } catch (err: any) {
    errorMessage.value = err.message || 'An unexpected error occurred during ingestion.'
  } finally {
    isSubmitting.value = false
    progressStatus.value = ''
  }
}

const resetForm = () => {
  ingestResults.value = null
  selectedFile.value = null
  urlsInput.value = ''
  textInput.value = ''
  overrideTitle.value = ''
  overrideCompany.value = ''
  overrideLocation.value = ''
  errorMessage.value = ''
}

const closeModal = () => {
  resetForm()
  emit('close')
}
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn"
    @click.self="closeModal"
  >
    <div
      class="relative w-full max-w-3xl bg-dark-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] transition-all"
    >
      <!-- Modal Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-dark-950/60">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white shadow-glow-blue">
            <UploadCloud class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <span>Ingest Opportunities</span>
              <span class="text-[10px] font-mono py-0.5 px-2 rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/30">
                Pipeline Ingestion
              </span>
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">
              Feed custom jobs into the engine for full automated scraping, scoring, and tailoring.
            </p>
          </div>
        </div>
        <button
          @click="closeModal"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Result State View -->
      <div v-if="ingestResults" class="p-6 overflow-y-auto space-y-5 flex-1">
        <!-- Results Summary Banner -->
        <div class="p-4 rounded-xl bg-gradient-to-br from-emerald-500/10 via-dark-850 to-dark-900 border border-emerald-500/30">
          <div class="flex items-center gap-2.5 text-emerald-400 font-semibold text-sm">
            <CheckCircle2 class="w-5 h-5 shrink-0" />
            <span>Ingestion Pipeline Complete</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-white/5">
              <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Received</span>
              <p class="text-lg font-mono font-bold text-white mt-0.5">{{ ingestResults.total_received }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-emerald-500/20">
              <span class="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Queued for AI</span>
              <p class="text-lg font-mono font-bold text-emerald-300 mt-0.5">{{ ingestResults.total_queued }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-amber-500/20">
              <span class="text-[10px] uppercase font-bold text-amber-400 tracking-wider">Duplicates</span>
              <p class="text-lg font-mono font-bold text-amber-300 mt-0.5">{{ ingestResults.total_duplicates }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-red-500/20">
              <span class="text-[10px] uppercase font-bold text-red-400 tracking-wider">Rejected / Skipped</span>
              <p class="text-lg font-mono font-bold text-red-300 mt-0.5">{{ ingestResults.total_rejected }}</p>
            </div>
          </div>
        </div>

        <!-- Ingested Job Items List -->
        <div class="space-y-2.5">
          <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Job Items Summary</h3>
          <div class="space-y-2 max-h-72 overflow-y-auto pr-1">
            <div
              v-for="(item, idx) in ingestResults.results"
              :key="idx"
              class="p-3 rounded-xl bg-dark-850 border border-white/5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:border-white/10 transition-colors"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-white text-xs truncate">{{ item.job_title }}</span>
                  <span class="text-[11px] text-slate-400">@ {{ item.company_name }}</span>
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span
                    class="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full"
                    :class="{
                      'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20': item.action_taken === 'queued_for_llm',
                      'bg-amber-500/10 text-amber-400 border border-amber-500/20': item.action_taken === 'duplicate_skipped',
                      'bg-red-500/10 text-red-400 border border-red-500/20': item.action_taken === 'filter_rejected' || item.action_taken === 'error'
                    }"
                  >
                    {{ item.action_taken === 'queued_for_llm' ? 'Queued for Tailoring' : item.action_taken }}
                  </span>
                  <span v-if="item.error_message" class="text-[11px] text-slate-400 truncate max-w-xs">
                    {{ item.error_message }}
                  </span>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <NuxtLink
                  v-if="item.id"
                  :to="`/execute/${item.id}`"
                  @click="closeModal"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-sm transition-all"
                >
                  <span>Open Triage</span>
                  <ChevronRight class="w-3.5 h-3.5" />
                </NuxtLink>
              </div>
            </div>
          </div>
        </div>

        <!-- Result Action Bar -->
        <div class="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
          <button
            @click="resetForm"
            class="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-300 text-xs font-semibold transition-colors"
          >
            Ingest More Jobs
          </button>
          <button
            @click="closeModal"
            class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors shadow-glow-green"
          >
            Done & View Triage Feed
          </button>
        </div>
      </div>

      <!-- Main Input Tabs & Form -->
      <div v-else class="flex flex-col flex-1 overflow-hidden">
        <!-- Tab Bar -->
        <div class="flex border-b border-white/10 px-6 bg-dark-950/40">
          <button
            @click="activeTab = 'file'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'file' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <FileSpreadsheet class="w-4 h-4" />
            <span>Upload File (PDF / CSV / XLSX)</span>
          </button>
          <button
            @click="activeTab = 'urls'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'urls' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <Link2 class="w-4 h-4" />
            <span>Job Links (URLs)</span>
          </button>
          <button
            @click="activeTab = 'text'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'text' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <FileText class="w-4 h-4" />
            <span>Paste Description</span>
          </button>
        </div>

        <!-- Tab Content Body -->
        <div class="p-6 overflow-y-auto flex-1 space-y-5">
          <!-- Error alert -->
          <div
            v-if="errorMessage"
            class="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-2 animate-fadeIn"
          >
            <AlertCircle class="w-4 h-4 text-red-400 shrink-0" />
            <span>{{ errorMessage }}</span>
          </div>

          <!-- TAB 1: File Upload -->
          <div v-if="activeTab === 'file'" class="space-y-4">
            <div
              @dragover="onDragOver"
              @dragleave="onDragLeave"
              @drop="onDrop"
              @click="fileInputRef?.click()"
              class="border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all"
              :class="isDragging ? 'border-brand-500 bg-brand-500/10' : 'border-white/10 hover:border-white/20 bg-dark-850/50'"
            >
              <input
                ref="fileInputRef"
                type="file"
                accept=".pdf,.csv,.xlsx,.xls"
                class="hidden"
                @change="onFileChange"
              />

              <div class="p-3.5 rounded-2xl bg-dark-800 border border-white/10 mb-3 text-brand-400 shadow-inner">
                <UploadCloud class="w-7 h-7 animate-pulse" />
              </div>

              <div class="space-y-1">
                <p class="text-sm font-semibold text-white">
                  Drop your job opportunity file here, or <span class="text-brand-400 underline decoration-brand-500/40">browse</span>
                </p>
                <p class="text-xs text-slate-400">
                  Accepts PDF (.pdf), CSV spreadsheets (.csv), and Excel workbooks (.xlsx) up to 15MB
                </p>
              </div>

              <div class="flex items-center gap-2 mt-4">
                <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">PDF</span>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">CSV</span>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">XLSX</span>
              </div>
            </div>

            <!-- File Selected Card -->
            <div
              v-if="selectedFile"
              class="flex items-center justify-between p-3.5 rounded-xl bg-dark-850 border border-brand-500/30"
            >
              <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-brand-500/20 text-brand-400">
                  <FileSpreadsheet class="w-5 h-5" />
                </div>
                <div>
                  <p class="text-xs font-semibold text-white truncate max-w-xs sm:max-w-md">{{ selectedFile.name }}</p>
                  <p class="text-[10px] text-slate-400">{{ formatFileSize(selectedFile.size) }}</p>
                </div>
              </div>
              <button
                @click.stop="clearSelectedFile"
                class="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Remove file"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>

            <div class="p-3 rounded-xl bg-dark-850/60 border border-white/5 text-[11px] text-slate-400 space-y-1">
              <p class="font-semibold text-slate-300 flex items-center gap-1.5">
                <Sparkles class="w-3.5 h-3.5 text-brand-400" />
                <span>Automatic Intelligent Parsing</span>
              </p>
              <p>For spreadsheets, columns matching "title", "company", "description", and "url" are automatically detected. For PDFs, text is extracted and parsed into full role assets.</p>
            </div>
          </div>

          <!-- TAB 2: Links / URLs -->
          <div v-if="activeTab === 'urls'" class="space-y-4">
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-xs font-semibold text-slate-300">Job Posting Links (One URL per line)</label>
                <span class="text-[10px] text-slate-500 font-mono">Greenhouse, Lever, Ashby, Workable, LinkedIn, Career Pages</span>
              </div>
              <textarea
                v-model="urlsInput"
                rows="6"
                placeholder="https://boards.greenhouse.io/stripe/jobs/1234567&#10;https://jobs.lever.co/figma/abcdef12-3456&#10;https://jobs.ashbyhq.com/posthog/..."
                class="w-full p-3 bg-dark-950 border border-white/10 rounded-xl text-xs text-white placeholder-slate-600 font-mono focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>

            <div class="p-3 rounded-xl bg-dark-850/60 border border-white/5 text-[11px] text-slate-400 flex items-start gap-2.5">
              <Sparkles class="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
              <div>
                <p class="font-semibold text-slate-300">Live Web Scraping & Extraction</p>
                <p class="mt-0.5">The engine will fetch each page, strip navigation and footers, extract the job description, company name, location, and detected tech stack with SSRF protection.</p>
              </div>
            </div>
          </div>

          <!-- TAB 3: Paste Text Description -->
          <div v-if="activeTab === 'text'" class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="text-[11px] font-medium text-slate-400">Job Title (Optional)</label>
                <input
                  v-model="overrideTitle"
                  type="text"
                  placeholder="e.g. Senior Frontend Engineer"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label class="text-[11px] font-medium text-slate-400">Company Name (Optional)</label>
                <input
                  v-model="overrideCompany"
                  type="text"
                  placeholder="e.g. Acme Corp"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label class="text-[11px] font-medium text-slate-400">Location (Optional)</label>
                <input
                  v-model="overrideLocation"
                  type="text"
                  placeholder="e.g. Remote / London"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <label class="text-xs font-semibold text-slate-300">Job Description / Postings Content</label>
                <span class="text-[10px] text-slate-500">Leave title/company blank for AI auto-detection</span>
              </div>
              <textarea
                v-model="textInput"
                rows="8"
                placeholder="Paste the raw job description or multiple job postings here...&#10;&#10;Tip: To paste multiple jobs in one go, separate each role with '---'"
                class="w-full p-3 bg-dark-950 border border-white/10 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>
          </div>

          <!-- Pipeline Controls & Switches -->
          <div class="pt-3 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label class="flex items-center gap-3 p-3 rounded-xl bg-dark-850/60 border border-white/5 cursor-pointer hover:border-white/10 transition-colors">
              <input
                v-model="bypassFilter"
                type="checkbox"
                class="w-4 h-4 rounded text-brand-500 bg-dark-900 border-white/20 focus:ring-brand-500"
              />
              <div>
                <div class="text-xs font-semibold text-white flex items-center gap-1.5">
                  <span>Bypass Pre-Filter</span>
                  <span class="text-[9px] font-mono py-0.2 px-1.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Recommended</span>
                </div>
                <p class="text-[10px] text-slate-400 mt-0.5">Ingests all roles without strict title/stack exclusion.</p>
              </div>
            </label>

            <label class="flex items-center gap-3 p-3 rounded-xl bg-dark-850/60 border border-white/5 cursor-pointer hover:border-white/10 transition-colors">
              <input
                v-model="tailorNow"
                type="checkbox"
                class="w-4 h-4 rounded text-brand-500 bg-dark-900 border-white/20 focus:ring-brand-500"
              />
              <div>
                <div class="text-xs font-semibold text-white flex items-center gap-1.5">
                  <span>Queue LLM Tailoring</span>
                  <Sparkles class="w-3.5 h-3.5 text-amber-400" />
                </div>
                <p class="text-[10px] text-slate-400 mt-0.5">Calculates fit score, generates cover letters & PDFs.</p>
              </div>
            </label>
          </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="px-6 py-4 border-t border-white/10 bg-dark-950/60 flex items-center justify-between">
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span v-if="isSubmitting" class="flex items-center gap-2 text-brand-400 font-medium">
              <Loader2 class="w-4 h-4 animate-spin" />
              <span>{{ progressStatus || 'Processing jobs...' }}</span>
            </span>
          </div>

          <div class="flex items-center gap-3">
            <button
              @click="closeModal"
              :disabled="isSubmitting"
              class="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-300 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              @click="handleSubmit"
              :disabled="isSubmitting"
              class="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-glow-blue transition-all disabled:opacity-50"
            >
              <Loader2 v-if="isSubmitting" class="w-4 h-4 animate-spin" />
              <UploadCloud v-else class="w-4 h-4" />
              <span>{{ isSubmitting ? 'Ingesting Opportunities...' : 'Start Ingestion Pipeline' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
