<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Zap, Play, CheckCircle2, Flame, RefreshCw } from 'lucide-vue-next'

interface Metrics {
  today_applied: number
  daily_target: number
  remaining: number
  queued_ready: number
  weekly_streak: number
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase ?? 'http://localhost:8000'

const metrics = ref<Metrics>({
  today_applied: 0,
  daily_target: 50,
  remaining: 50,
  queued_ready: 0,
  weekly_streak: 1
})

const isScraping = ref(false)
const scrapeMessage = ref('')
let timer: any = null

const fetchMetrics = async () => {
  try {
    const res = await fetch(`${apiBase}/api/metrics/daily`)
    if (res.ok) {
      metrics.value = await res.json()
    }
  } catch (err) {
    console.error('Failed to load metrics:', err)
  }
}

const progressPercentage = computed(() => {
  const target = metrics.value.daily_target || 50
  return Math.min(100, Math.round((metrics.value.today_applied / target) * 100))
})

const isOnTrack = computed(() => {
  return progressPercentage.value >= 40 || metrics.value.today_applied >= 10
})

const triggerScrapers = async () => {
  if (isScraping.value) return
  isScraping.value = true
  scrapeMessage.value = 'Triggering crawlers...'
  try {
    const res = await fetch(`${apiBase}/api/metrics/scrapers/trigger`, { method: 'POST' })
    if (res.ok) {
      scrapeMessage.value = 'Scrapers enqueued!'
      setTimeout(() => {
        fetchMetrics()
        scrapeMessage.value = ''
      }, 3000)
    }
  } catch (err) {
    scrapeMessage.value = 'Failed to trigger'
  } finally {
    setTimeout(() => {
      isScraping.value = false
    }, 2000)
  }
}

onMounted(() => {
  fetchMetrics()
  timer = setInterval(fetchMetrics, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <header class="sticky top-0 z-50 glass-panel border-b border-white/10 px-4 lg:px-8 py-3 transition-all">
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
      
      <!-- Logo & Profile Identity -->
      <div class="flex items-center gap-3">
        <NuxtLink to="/" class="flex items-center gap-2 group">
          <div class="h-9 w-9 rounded-lg bg-gradient-to-br from-brand-600 to-emerald-500 flex items-center justify-center shadow-glow-blue transition-transform group-hover:scale-105">
            <Zap class="w-5 h-5 text-white fill-white" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-extrabold tracking-tight text-white text-base">JATE</span>
              <span class="text-xs font-mono uppercase px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-500 border border-brand-500/30">Cockpit</span>
            </div>
            <p class="text-[11px] text-slate-400 font-medium">Emmanuel Okeibunor &bull; 50 Apps/Day Target</p>
          </div>
        </NuxtLink>
      </div>

      <!-- Center Progress Meter -->
      <div class="flex-1 max-w-lg w-full">
        <div class="flex items-center justify-between text-xs mb-1.5 font-medium">
          <div class="flex items-center gap-2">
            <span class="text-slate-300">Daily Velocity:</span>
            <span class="text-white font-bold font-mono">{{ metrics.today_applied }} / {{ metrics.daily_target }}</span>
            <span class="text-slate-400 text-[11px]">({{ metrics.remaining }} to go)</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span v-if="isOnTrack" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 animate-pulse-subtle">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              On Track
            </span>
            <span class="text-slate-400 font-mono text-[11px]">{{ progressPercentage }}%</span>
          </div>
        </div>

        <!-- Custom Progress Track -->
        <div class="h-2.5 w-full bg-dark-850 rounded-full overflow-hidden p-0.5 border border-white/5">
          <div
            class="h-full rounded-full transition-all duration-700 ease-out bg-gradient-to-r from-brand-500 via-indigo-500 to-emerald-400 shadow-glow-green"
            :style="{ width: `${progressPercentage}%` }"
          ></div>
        </div>
      </div>

      <!-- Right Action Badges & Scraper Trigger -->
      <div class="flex items-center gap-3">
        <!-- Streak Counter -->
        <div class="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-850 border border-white/5 text-xs text-amber-400 font-medium">
          <Flame class="w-4 h-4 fill-amber-400" />
          <span>{{ metrics.weekly_streak }}d Streak</span>
        </div>

        <!-- Queued Ready Count -->
        <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-850 border border-white/5 text-xs text-brand-400 font-medium font-mono">
          <CheckCircle2 class="w-3.5 h-3.5 text-brand-400" />
          <span>{{ metrics.queued_ready }} Ready</span>
        </div>

        <!-- Run Scrapers Button -->
        <button
          @click="triggerScrapers"
          :disabled="isScraping"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-xs font-semibold border border-white/15 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isScraping }" />
          <span>{{ isScraping ? 'Crawling...' : 'Run Scrapers' }}</span>
        </button>
      </div>

    </div>
  </header>
</template>
