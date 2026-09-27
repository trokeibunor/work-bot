<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, ExternalLink, Download, CheckCircle2, ChevronRight,
  Building2, MapPin, Sparkles, AlertCircle, Eye, Archive,
  EyeOff, RotateCcw, Mail, Rocket
} from 'lucide-vue-next'
import AssetCopier from '~/components/AssetCopier.vue'

const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()
const apiBase = config.public.apiBase ?? 'http://localhost:8000'

const jobId = route.params.id as string
const job = ref<any>(null)
const loading = ref(true)
const isApplying = ref(false)
const isIgnoring = ref(false)
const errorMsg = ref('')

const fetchJob = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`${apiBase}/api/jobs/${jobId}`)
    if (!res.ok) throw new Error('Job details not found')
    job.value = await res.json()
  } catch (err: any) {
    errorMsg.value = err.message || 'Error loading job'
  } finally {
    loading.value = false
  }
}

const downloadPdf = () => {
  window.open(`${apiBase}/api/assets/${jobId}/pdf`, '_blank')
}

const openApplicationPortal = () => {
  if (job.value?.source_url) {
    window.open(job.value.source_url, '_blank')
  }
}

const markAsAppliedAndNext = async () => {
  if (isApplying.value) return
  isApplying.value = true
  try {
    // 1. Update status to applied
    await fetch(`${apiBase}/api/jobs/${jobId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'applied' })
    })

    // 2. Fetch next ready-to-apply job
    const listRes = await fetch(`${apiBase}/api/jobs?status=ready_to_apply&limit=10`)
    if (listRes.ok) {
      const data = await listRes.json()
      const remainingJobs = Array.isArray(data) ? data : (data.items || [])
      const next = remainingJobs.find((j: any) => j.id !== jobId)
      if (next) {
        router.push(`/execute/${next.id}`)
        return
      }
    }
    // If no more jobs left in queue, return to dashboard
    router.push('/')
  } catch (err) {
    console.error('Failed to mark applied:', err)
  } finally {
    isApplying.value = false
  }
}

const ignoreJobAndNext = async () => {
  if (isIgnoring.value) return
  isIgnoring.value = true
  try {
    await fetch(`${apiBase}/api/jobs/${jobId}/ignore`, {
      method: 'POST'
    })
    const listRes = await fetch(`${apiBase}/api/jobs?status=ready_to_apply&limit=10`)
    if (listRes.ok) {
      const data = await listRes.json()
      const remaining = Array.isArray(data) ? data : (data.items || [])
      const next = remaining.find((j: any) => j.id !== jobId)
      if (next) {
        router.push(`/execute/${next.id}`)
        return
      }
    }
    router.push('/')
  } catch (err) {
    console.error('Error ignoring:', err)
  } finally {
    isIgnoring.value = false
  }
}

const unignoreJob = async () => {
  try {
    await fetch(`${apiBase}/api/jobs/${jobId}/unignore`, {
      method: 'POST'
    })
    await fetchJob()
  } catch (err) {
    console.error('Error unignoring:', err)
  }
}

// Global Keyboard Shortcut: Cmd + Enter (Apply), Esc (Ignore)
const handleGlobalKeydown = (e: KeyboardEvent) => {
  if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
    return
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    markAsAppliedAndNext()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    ignoreJobAndNext()
  }
}

onMounted(() => {
  fetchJob()
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Top Cockpit Breadcrumb & Quick Actions -->
    <div class="flex items-center justify-between">
      <NuxtLink to="/" class="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors">
        <ArrowLeft class="w-4 h-4" />
        <span>Back to Triage Queue</span>
      </NuxtLink>

      <div class="flex items-center gap-2">
        <span class="text-[11px] text-slate-500 font-mono hidden md:inline">
          Shortcuts: <kbd class="px-1.5 py-0.5 rounded bg-dark-900 border border-white/10 text-white font-mono">&cmd; + Enter</kbd> Apply &bull; <kbd class="px-1.5 py-0.5 rounded bg-dark-900 border border-white/10 text-white font-mono">Esc</kbd> Ignore
        </span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="p-16 text-center text-slate-400 glass-panel rounded-xl">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-2 border-brand-500 border-t-transparent mb-3"></div>
      <p class="text-sm">Loading execution cockpit...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="errorMsg" class="p-8 text-center glass-panel rounded-xl text-red-400">
      <AlertCircle class="w-10 h-10 mx-auto mb-2 text-red-400" />
      <p class="text-sm font-semibold">{{ errorMsg }}</p>
      <NuxtLink to="/" class="mt-4 inline-block px-4 py-2 rounded-lg bg-brand-600 text-white text-xs font-semibold">
        Return to Queue
      </NuxtLink>
    </div>

    <!-- Main Cockpit Split Pane -->
    <div v-else-if="job" class="space-y-6">
      
      <!-- Cockpit Header Banner -->
      <div class="glass-panel p-5 rounded-xl border border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-xl font-extrabold text-white tracking-tight">
              {{ job.company_name }}
            </h1>
            <span class="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-dark-850 text-brand-400 border border-brand-500/20 font-semibold">
              {{ job.source }}
            </span>
            <span
              class="font-mono font-bold text-xs px-2.5 py-0.5 rounded border"
              :class="job.match_score >= 80 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-blue-500/15 text-blue-400 border-blue-500/30'"
            >
              {{ job.match_score }}% Match
            </span>
            <span
              v-if="job.is_founder_led"
              class="px-2.5 py-0.5 rounded text-xs bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 font-bold shadow-sm"
              title="Direct founder or founding engineering team opportunity"
            >
              <Rocket class="w-3.5 h-3.5 text-amber-400" />
              Founder-Led
            </span>
            <span v-if="job.status === 'archived'" class="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-dark-800 text-slate-400 border border-white/10">
              Ignored
            </span>
          </div>
          <div class="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-slate-300">
            <span class="font-semibold text-slate-200">{{ job.job_title }}</span>
            <span class="text-slate-500">&bull;</span>
            <span class="flex items-center gap-1 text-slate-400">
              <MapPin class="w-3.5 h-3.5 text-slate-500" />
              {{ job.location_raw || 'Remote / Relocation' }}
            </span>
          </div>

          <!-- Direct Hiring Email or Follow-up Inbox Banner -->
          <div v-if="job.hiring_contacts?.primary_email" class="flex flex-wrap items-center gap-2 mt-2.5 pt-2 border-t border-white/5">
            <span
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium border"
              :class="job.hiring_contacts.is_direct_listing_email
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                : 'bg-dark-850 text-slate-300 border-white/10'"
            >
              <Mail class="w-3.5 h-3.5" :class="job.hiring_contacts.is_direct_listing_email ? 'text-emerald-400' : 'text-slate-400'" />
              <span class="text-slate-400 text-[11px]">{{ job.hiring_contacts.is_direct_listing_email ? 'Direct Hiring Email:' : 'Talent Inbox:' }}</span>
              <strong class="text-white select-all">{{ job.hiring_contacts.primary_email }}</strong>
            </span>

            <a
              :href="job.hiring_contacts.mailto_url || `mailto:${job.hiring_contacts.primary_email}`"
              target="_blank"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/15 text-slate-200 text-xs transition-colors"
            >
              <ExternalLink class="w-3 h-3 text-slate-400" />
              <span>Compose Email</span>
            </a>
          </div>
        </div>

        <!-- External Link & PDF Download Actions -->
        <div class="flex items-center gap-2.5 w-full md:w-auto">
          <button
            @click="openApplicationPortal"
            class="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white text-xs font-semibold border border-white/15 transition-all active:scale-95 shadow-sm"
          >
            <span>Open Application Portal</span>
            <ExternalLink class="w-3.5 h-3.5 text-slate-300" />
          </button>

          <button
            @click="downloadPdf"
            class="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-glow-green transition-all active:scale-95"
          >
            <Download class="w-3.5 h-3.5" />
            <span>Download Tailored PDF</span>
          </button>
        </div>
      </div>

      <!-- Split Grid: Left Details & Right Asset Copier -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        <!-- Left Pane: Role Overview & Raw Description (5 Cols) -->
        <div class="lg:col-span-5 space-y-4">
          
          <!-- Match Rationale Card -->
          <div class="glass-card p-4 rounded-xl border border-white/10 space-y-2">
            <div class="flex items-center gap-2 text-xs font-bold text-brand-400">
              <Sparkles class="w-4 h-4 text-brand-400" />
              <span>Tailoring Fit & Strategy</span>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed italic">
              &ldquo;{{ job.match_reasoning || 'Strong fit with Emmanuel\'s full-stack stack (Vue/Nuxt, Python/FastAPI, Golang).' }}&rdquo;
            </p>
            <div class="flex flex-wrap gap-1.5 pt-2 border-t border-white/5">
              <span
                v-for="tag in job.tech_stack_tags"
                :key="tag"
                class="px-2 py-0.5 rounded bg-dark-900 text-slate-300 border border-white/5 text-[11px] font-mono"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- Raw Job Description Box -->
          <div class="glass-panel p-4 rounded-xl border border-white/10 space-y-3">
            <span class="text-xs font-bold text-slate-300">Job Description Preview</span>
            <div class="max-h-[500px] overflow-y-auto text-xs text-slate-400 font-sans leading-relaxed whitespace-pre-line pr-2 border-t border-white/5 pt-3">
              {{ job.description_raw }}
            </div>
          </div>

        </div>

        <!-- Right Pane: Asset Copier & Screening Answers (7 Cols) -->
        <div class="lg:col-span-7">
          <AssetCopier
            v-if="job.assets"
            :jobId="job.id"
            :assets="job.assets"
            :hiringContacts="job.hiring_contacts"
            :companyName="job.company_name"
            :jobTitle="job.job_title"
            :source="job.source"
            :sourceUrl="job.source_url"
            :isFounderLed="job.is_founder_led"
            @updated="fetchJob"
          />
          <div v-else class="glass-panel p-8 rounded-xl text-center text-slate-400">
            <p class="text-xs">Generating assets for this job...</p>
          </div>
        </div>

      </div>

      <!-- Bottom Sticky Action Bar -->
      <div class="sticky bottom-4 z-40 glass-panel p-4 rounded-xl border border-white/15 shadow-glass flex items-center justify-between gap-4">
        <div>
          <button
            v-if="job.status === 'archived'"
            @click="unignoreJob"
            class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 hover:text-white text-xs font-semibold border border-white/10 transition-colors"
          >
            <RotateCcw class="w-3.5 h-3.5 text-brand-400" />
            <span>Restore Listing to Active Queue</span>
          </button>

          <button
            v-else
            @click="ignoreJobAndNext"
            :disabled="isIgnoring"
            class="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-dark-900 hover:bg-red-500/15 text-slate-400 hover:text-red-400 text-xs font-semibold border border-white/10 hover:border-red-500/30 transition-all disabled:opacity-50"
            title="Ignore listing (hide from active queue and jump to next)"
          >
            <EyeOff class="w-3.5 h-3.5" :class="{ 'animate-pulse': isIgnoring }" />
            <span>{{ isIgnoring ? 'Ignoring...' : 'Ignore Listing (Esc)' }}</span>
          </button>
        </div>

        <div class="flex items-center gap-3">
          <button
            @click="markAsAppliedAndNext"
            :disabled="isApplying"
            class="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold text-xs tracking-wide shadow-glow-green transition-all active:scale-95 disabled:opacity-50"
          >
            <CheckCircle2 class="w-4 h-4 text-white" />
            <span>{{ isApplying ? 'Submitting & Advancing...' : 'Mark as Applied (Cmd + Enter)' }}</span>
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
      </div>

    </div>
  </div>
</template>
