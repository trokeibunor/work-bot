<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
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

const dialogRef = ref<HTMLDialogElement | null>(null)
let previousFocus: HTMLElement | null = null
let previousOverflow = ''
const trapFocus = (event: KeyboardEvent) => {
  if (event.key !== 'Tab') return
  const controls = [...(dialogRef.value?.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex="0"]') || [])]
    .filter(element => !element.hasAttribute('disabled') && !element.closest('[inert]') && element.getClientRects().length > 0)
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
const releaseDialog = () => {
  dialogRef.value?.close()
  document.body.style.overflow = previousOverflow
  previousFocus?.focus()
  previousFocus = null
}
watch(() => props.show, (show) => {
  if (show) {
    previousFocus = document.activeElement as HTMLElement
    previousOverflow = document.body.style.overflow
    dialogRef.value?.showModal()
    document.body.style.overflow = 'hidden'
  } else if (dialogRef.value?.open) releaseDialog()
}, { flush: 'post' })
onBeforeUnmount(() => { if (dialogRef.value?.open) releaseDialog() })

type ActiveTab = 'file' | 'urls' | 'text'
const activeTab = ref<ActiveTab>('urls')

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
    clearSelectedFile()
    errorMessage.value = `Unsupported file format ".${ext}". Please upload a .pdf, .csv, or .xlsx file.`
    return
  }
  if (file.size > 15 * 1024 * 1024) {
    clearSelectedFile()
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

const urlLines = computed(() => urlsInput.value.split('\n').map(line => line.trim()).filter(Boolean))
const invalidUrls = computed(() => urlLines.value.filter(line => { try { const url = new URL(line); return !['http:', 'https:'].includes(url.protocol) || !url.hostname } catch { return true } }))
const canSubmit = computed(() => activeTab.value === 'file' ? !!selectedFile.value : activeTab.value === 'text' ? textInput.value.trim().length >= 20 : urlLines.value.length > 0 && invalidUrls.value.length === 0 && urlLines.value.length <= 100)
watch(activeTab, () => { errorMessage.value = '' })

// Submissions
const handleSubmit = async () => {
  if (isSubmitting.value || !canSubmit.value) return
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
      const urlList = [...new Set(urlLines.value)]

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
  clearSelectedFile()
  urlsInput.value = ''
  textInput.value = ''
  overrideTitle.value = ''
  overrideCompany.value = ''
  overrideLocation.value = ''
  errorMessage.value = ''
}

const closeModal = () => {
  if (isSubmitting.value) return
  resetForm()
  emit('close')
}
</script>

<template>
  <dialog
    ref="dialogRef"
    aria-labelledby="ingest-title"
    aria-describedby="ingest-description"
    aria-modal="true"
    role="dialog"
    class="ingest-dialog"
    @keydown="trapFocus"
    @cancel.prevent="closeModal"
    @click.self="closeModal"
  >
    <div
      class="ingest-panel relative w-full max-w-3xl bg-dark-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] transition-all"
    >
      <!-- Modal Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-dark-950/60">
        <div class="flex items-center gap-3">
          <div class="p-2 rounded-xl bg-brand-600 text-white ">
            <UploadCloud class="w-5 h-5" />
          </div>
          <div>
            <h2 id="ingest-title" class="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <span>Add jobs</span>
            </h2>
            <p id="ingest-description" class="text-sm text-slate-400 mt-0.5">
              Add a file, paste links, or bring a job description into your queue.
            </p>
          </div>
        </div>
        <button
          @click="closeModal"
          :disabled="isSubmitting"
          aria-label="Close add jobs"
          autofocus
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
            <span>Import complete</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-white/5">
              <span class="text-xs uppercase font-bold text-slate-400 tracking-wider">Received</span>
              <p class="text-lg font-mono font-bold text-white mt-0.5">{{ ingestResults.total_received }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-emerald-500/20">
              <span class="text-xs uppercase font-bold text-emerald-400 tracking-wider">Preparing materials</span>
              <p class="text-lg font-mono font-bold text-emerald-300 mt-0.5">{{ ingestResults.total_queued }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-amber-500/20">
              <span class="text-xs uppercase font-bold text-amber-400 tracking-wider">Duplicates</span>
              <p class="text-lg font-mono font-bold text-amber-300 mt-0.5">{{ ingestResults.total_duplicates }}</p>
            </div>
            <div class="p-2.5 rounded-lg bg-dark-900/80 border border-red-500/20">
              <span class="text-xs uppercase font-bold text-red-400 tracking-wider">Rejected / Skipped</span>
              <p class="text-lg font-mono font-bold text-red-300 mt-0.5">{{ ingestResults.total_rejected }}</p>
            </div>
          </div>
        </div>

        <!-- Ingested Job Items List -->
        <div class="space-y-2.5">
          <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Import results</h3>
          <div class="space-y-2 max-h-72 overflow-y-auto pr-1">
            <div
              v-for="(item, idx) in ingestResults.results"
              :key="idx"
              class="p-3 rounded-xl bg-dark-850 border border-white/5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:border-white/10 transition-colors"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-white text-xs truncate">{{ item.job_title }}</span>
                  <span class="text-xs text-slate-400">@ {{ item.company_name }}</span>
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span
                    class="text-xs font-mono font-medium px-2 py-0.5 rounded-full"
                    :class="{
                      'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20': item.action_taken === 'queued_for_llm',
                      'bg-amber-500/10 text-amber-400 border border-amber-500/20': item.action_taken === 'duplicate_skipped',
                      'bg-red-500/10 text-red-400 border border-red-500/20': item.action_taken === 'filter_rejected' || item.action_taken === 'error'
                    }"
                  >
                    {{ ({queued_for_llm:'Preparing materials',saved:'Saved for later',duplicate_skipped:'Already saved',filter_rejected:'Outside your filters',error:'Could not import'} as Record<string,string>)[item.action_taken] || item.action_taken }}
                  </span>
                  <span v-if="item.error_message" class="text-xs text-slate-400 truncate max-w-xs">
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
                  <span>Review job</span>
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
            Add more jobs
          </button>
          <button
            @click="closeModal"
            class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors shadow-glow-green"
          >
            Done
          </button>
        </div>
      </div>

      <!-- Main Input Tabs & Form -->
      <div v-else class="flex flex-col flex-1 overflow-hidden">
        <!-- Tab Bar -->
        <div class="ingest-tabs flex border-b border-white/10 px-6 bg-dark-950/40" :inert="isSubmitting" role="group" aria-label="How to add jobs">
          <button
            @click="activeTab = 'file'" :aria-pressed="activeTab === 'file'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'file' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <FileSpreadsheet class="w-4 h-4" />
            <span>File</span>
          </button>
          <button
            @click="activeTab = 'urls'" :aria-pressed="activeTab === 'urls'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'urls' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <Link2 class="w-4 h-4" />
            <span>Links</span>
          </button>
          <button
            @click="activeTab = 'text'" :aria-pressed="activeTab === 'text'"
            class="flex items-center gap-2 py-3 px-4 text-xs font-semibold border-b-2 transition-all"
            :class="activeTab === 'text' ? 'border-brand-500 text-brand-400 bg-brand-500/5' : 'border-transparent text-slate-400 hover:text-white'"
          >
            <FileText class="w-4 h-4" />
            <span>Text</span>
          </button>
        </div>

        <!-- Tab Content Body -->
        <div class="ingest-body p-6 overflow-y-auto flex-1 space-y-5" :inert="isSubmitting">
          <!-- Error alert -->
          <div
            v-if="errorMessage"
            role="alert"
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
              role="button" tabindex="0" aria-label="Choose a PDF, CSV, or Excel file"
              @keydown.enter.prevent="fileInputRef?.click()"
              @keydown.space.prevent="fileInputRef?.click()"
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
                <UploadCloud class="w-7 h-7" />
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
                <span class="text-xs font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">PDF</span>
                <span class="text-xs font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">CSV</span>
                <span class="text-xs font-mono px-2 py-0.5 rounded bg-dark-800 text-slate-300 border border-white/5">XLSX</span>
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
                  <p class="text-xs text-slate-400">{{ formatFileSize(selectedFile.size) }}</p>
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

            <div class="p-3 rounded-xl bg-dark-850/60 border border-white/5 text-xs text-slate-400 space-y-1">
              <p class="font-semibold text-slate-300 flex items-center gap-1.5">
                <Sparkles class="w-3.5 h-3.5 text-brand-400" />
                <span>Import a list of opportunities</span>
              </p>
              <p>Use columns named title, company, description, and url in spreadsheets. PDFs should contain selectable text.</p>
            </div>
          </div>

          <!-- TAB 2: Links / URLs -->
          <div v-if="activeTab === 'urls'" class="space-y-4">
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <label for="ingest-urls" class="text-xs font-semibold text-slate-300">Job links</label>
                <span class="text-xs text-slate-400">One link per line · up to 100</span>
              </div>
              <textarea
                id="ingest-urls" aria-describedby="ingest-url-feedback" :aria-invalid="invalidUrls.length > 0" v-model="urlsInput"
                rows="6"
                placeholder="https://boards.greenhouse.io/stripe/jobs/1234567&#10;https://jobs.lever.co/figma/abcdef12-3456&#10;https://jobs.ashbyhq.com/posthog/..."
                class="w-full p-3 bg-dark-950 border border-white/10 rounded-xl text-xs text-white placeholder-slate-600 font-mono focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>

            <p id="ingest-url-feedback" class="text-xs" :class="invalidUrls.length || urlLines.length > 100 ? 'text-red-300' : 'text-slate-400'">{{ invalidUrls.length ? `${invalidUrls.length} invalid link(s). Each line needs a complete http:// or https:// URL.` : urlLines.length > 100 ? 'Add no more than 100 links at a time.' : `${new Set(urlLines).size} unique links ready to import` }}</p>
            <div class="p-3 rounded-xl bg-dark-850/60 border border-white/5 text-xs text-slate-400 flex items-start gap-2.5">
              <Sparkles class="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
              <div>
                <p class="font-semibold text-slate-300">Bring in the original listing</p>
                <p class="mt-0.5">Use direct job links where possible. If a page requires login or cannot be read, paste its description in the Text tab.</p>
              </div>
            </div>
          </div>

          <!-- TAB 3: Paste Text Description -->
          <div v-if="activeTab === 'text'" class="space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label for="ingest-job-title" class="text-xs font-medium text-slate-400">Job Title (Optional)</label>
                <input
                  id="ingest-job-title" aria-label="Job title (optional)" v-model="overrideTitle"
                  type="text"
                  placeholder="e.g. Senior Frontend Engineer"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label for="ingest-company" class="text-xs font-medium text-slate-400">Company Name (Optional)</label>
                <input
                  id="ingest-company" aria-label="Company name (optional)" v-model="overrideCompany"
                  type="text"
                  placeholder="e.g. Acme Corp"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label for="ingest-location" class="text-xs font-medium text-slate-400">Location (Optional)</label>
                <input
                  id="ingest-location" aria-label="Location (optional)" v-model="overrideLocation"
                  type="text"
                  placeholder="e.g. Remote / London"
                  class="w-full mt-1 px-3 py-2 bg-dark-950 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <label for="ingest-description-text" class="text-xs font-semibold text-slate-300">Job description</label>
                <span class="text-xs text-slate-400">Leave title/company blank for AI auto-detection</span>
              </div>
              <textarea
                id="ingest-description-text" aria-label="Job description" v-model="textInput"
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
                class="w-4 h-4 rounded text-blue-300 bg-dark-900 border-white/20 focus:ring-brand-500"
              />
              <div>
                <div class="text-xs font-semibold text-white flex items-center gap-1.5">
                  <span>Keep all imported roles</span>

                </div>
                <p class="text-xs text-slate-400 mt-0.5">Include roles outside your usual technology filters.</p>
              </div>
            </label>

            <label class="flex items-center gap-3 p-3 rounded-xl bg-dark-850/60 border border-white/5 cursor-pointer hover:border-white/10 transition-colors">
              <input
                v-model="tailorNow"
                type="checkbox"
                class="w-4 h-4 rounded text-blue-300 bg-dark-900 border-white/20 focus:ring-brand-500"
              />
              <div>
                <div class="text-xs font-semibold text-white flex items-center gap-1.5">
                  <span>Prepare application materials</span>
                  <Sparkles class="w-3.5 h-3.5 text-amber-400" />
                </div>
                <p class="text-xs text-slate-400 mt-0.5">Assess fit and draft your documents. Turn off to save for later.</p>
              </div>
            </label>
          </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="ingest-footer px-6 py-4 border-t border-white/10 bg-dark-950/60 flex items-center justify-between">
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span v-if="isSubmitting" role="status" aria-live="polite" class="flex items-center gap-2 text-brand-400 font-medium">
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
              :disabled="isSubmitting || !canSubmit"
              class="flex items-center gap-2 px-5 py-2 rounded-xl bg-brand-600 hover:bg-blue-700 text-white text-xs font-semibold  transition-all disabled:opacity-50"
            >
              <Loader2 v-if="isSubmitting" class="w-4 h-4 animate-spin" />
              <UploadCloud v-else class="w-4 h-4" />
              <span>{{ isSubmitting ? 'Adding jobs…' : 'Add jobs' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </dialog>
</template>
