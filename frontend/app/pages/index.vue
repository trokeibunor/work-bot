<script setup lang="ts">
import { ref } from 'vue'
import JobQueueTable from '~/components/JobQueueTable.vue'
import { RefreshCw, Zap, Rocket, CheckCircle2 } from 'lucide-vue-next'

const config = useRuntimeConfig()
const apiBase = config.public.apiBase ?? 'http://localhost:8000'

const queueTableRef = ref<any>(null)
const tailoringInProgress = ref(false)
const isScrapingCommunity = ref(false)
const isRefreshing = ref(false)
const notificationMsg = ref('')

const triggerCommunityScraper = async () => {
  if (isScrapingCommunity.value) return
  isScrapingCommunity.value = true
  notificationMsg.value = ''
  try {
    const res = await fetch(`${apiBase}/api/metrics/scrapers/trigger-community`, { method: 'POST' })
    if (res.ok) {
      notificationMsg.value = 'Triggered high-priority Hacker News & Reddit founder scrapers!'
      setTimeout(() => { notificationMsg.value = '' }, 4000)
      // Wait a moment then refresh feed to show freshly discovered jobs
      setTimeout(async () => {
        await queueTableRef.value?.fetchStats()
        await queueTableRef.value?.fetchJobs(true)
      }, 2500)
    }
  } catch (err) {
    console.error('Failed to trigger community scrapers:', err)
  } finally {
    isScrapingCommunity.value = false
  }
}

const triggerTailorPending = async () => {
  if (tailoringInProgress.value) return
  tailoringInProgress.value = true
  try {
    await fetch(`${apiBase}/api/jobs/tailor-pending?limit=50`, { method: 'POST' })
    await queueTableRef.value?.fetchJobs(true)
    await queueTableRef.value?.fetchStats()
  } catch (err) {
    console.error('Failed to trigger tailoring:', err)
  } finally {
    tailoringInProgress.value = false
  }
}

const handleRefresh = async () => {
  isRefreshing.value = true
  try {
    await queueTableRef.value?.fetchStats()
    await queueTableRef.value?.fetchJobs(false)
  } finally {
    isRefreshing.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Hero Banner / Triage Headline -->
    <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-2 border-b border-white/5">
      <div>
        <h1 class="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
          <span>Triage Queue</span>
          <span class="text-xs font-mono py-0.5 px-2 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            High Velocity
          </span>
        </h1>
        <p class="text-xs text-slate-400 mt-1">
          Review, prioritize, and execute applications in under 2 minutes per role.
        </p>
      </div>

      <!-- Quick Metrics Ribbon -->
      <div class="flex flex-wrap items-center gap-2">
        <button
          @click="triggerCommunityScraper"
          :disabled="isScrapingCommunity"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-xs font-semibold shadow-glow-amber transition-all disabled:opacity-50"
          title="Scrape direct founder and engineering team hiring posts from Hacker News and Reddit"
        >
          <Rocket class="w-3.5 h-3.5" :class="{ 'animate-bounce': isScrapingCommunity }" />
          <span>{{ isScrapingCommunity ? 'Ingesting HN & Reddit...' : 'Scrape Founder & Community' }}</span>
        </button>

        <button
          @click="triggerTailorPending"
          :disabled="tailoringInProgress"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-glow-indigo transition-all disabled:opacity-50"
        >
          <Zap class="w-3.5 h-3.5" :class="{ 'animate-spin': tailoringInProgress }" />
          <span>{{ tailoringInProgress ? 'Dispatching...' : 'Tailor Pending' }}</span>
        </button>

        <button
          @click="handleRefresh"
          :disabled="isRefreshing"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-900 hover:bg-dark-850 text-slate-300 text-xs font-semibold border border-white/10 transition-colors"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isRefreshing }" />
          <span>Refresh Feed</span>
        </button>
      </div>
    </div>

    <!-- Feedback Notification -->
    <div
      v-if="notificationMsg"
      class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-medium flex items-center gap-2 animate-fadeIn"
    >
      <CheckCircle2 class="w-4 h-4 text-amber-400" />
      <span>{{ notificationMsg }}</span>
    </div>

    <!-- Main Triage Table with Server-Side Pagination and Date Filtering -->
    <JobQueueTable
      ref="queueTableRef"
      :api-base="apiBase"
    />
  </div>
</template>
