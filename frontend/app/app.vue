<script setup lang="ts">
import { LayoutGrid, FileText, Activity, Plus, X, UserRound } from 'lucide-vue-next'
const route = useRoute()
const candidateIdentity = useState('candidate-identity',()=>({name:'Candidate',version_id:''}))
const initials = computed(()=>candidateIdentity.value.name.split(/\s+/).slice(0,2).map(part=>part[0]).join(''))
const { apiBase, showIngest, metrics, counts, metricsError, notice, refreshMetrics, jobsChanged } = useWorkspace()
const links = [{ path: '/', label: 'Opportunities', icon: LayoutGrid }, { path: '/applications', label: 'Applications', icon: FileText }, { path: '/automation', label: 'Automation', icon: Activity }, { path:'/profile',label:'My Profile',icon:UserRound }]
const active = (path: string) => path === '/' ? route.path === '/' || route.path.startsWith('/execute/') : route.path === path
const title = computed(() => route.path.startsWith('/execute/') ? 'Prepare application' : links.find(link => active(link.path))?.label || 'Workspace')
const progress = computed(() => metrics.value ? Math.min(100, (metrics.value.today_applied / Math.max(1, metrics.value.daily_target)) * 100) : 0)
let timer: ReturnType<typeof setInterval>
onMounted(() => { apiRequest<{name:string,version_id:string}>(`${apiBase}/api/candidate/identity`).then(data=>candidateIdentity.value=data).catch(()=>{}); refreshMetrics(); timer = setInterval(() => { if (!document.hidden) refreshMetrics() }, 30000) })
onUnmounted(() => clearInterval(timer))
const ingested = (count: number) => { notice.value = `${count} opportunities added. Tailored materials will appear when ready.`; jobsChanged() }
</script>
<template>
  <div class="workspace-app">
    <a href="#main-content" class="skip-link">Skip to content</a>
    <aside class="sidebar" aria-label="Workspace navigation">
      <NuxtLink to="/" class="brand" aria-label="JATE home"><span class="brand-mark"><svg viewBox="0 0 28 32" aria-hidden="true"><path d="M21 3v17c0 7-5 10-11 8-4-1-5-4-5-7M13 3h12" /></svg></span>JATE</NuxtLink>
      <p class="space-label">Personal workspace</p>
      <nav class="nav"><NuxtLink v-for="link in links" :key="link.path" :to="link.path" :class="{ active: active(link.path) }" :aria-current="active(link.path) ? 'page' : undefined"><component :is="link.icon" aria-hidden="true" /><span class="nav-label">{{ link.label }}</span><span v-if="counts && ['/', '/applications'].includes(link.path)" class="nav-count">{{ (link.path === '/' ? counts.ready_to_apply : counts.applied).toLocaleString() }}</span></NuxtLink></nav>
      <div class="sidebar-bottom"><div class="daily"><div class="daily-title"><span>Today's progress</span><strong>{{ metrics ? `${metrics.today_applied} / ${metrics.daily_target}` : '—' }}</strong></div><div class="progress" role="progressbar" aria-label="Daily applications" :aria-valuenow="metrics?.today_applied || 0" :aria-valuemax="Math.max(metrics?.daily_target || 50, metrics?.today_applied || 0)" aria-valuemin="0"><span :style="{ width: `${progress}%` }" /></div><small>{{ metricsError || (metrics ? `${metrics.remaining} applications left to your goal.` : 'Loading your progress…') }}</small></div><NuxtLink to="/profile" class="profile"><div class="avatar">{{ initials }}</div><div><strong>{{ candidateIdentity.name }}</strong><small>Manage candidate profile</small></div></NuxtLink></div>
    </aside>
    <div class="main">
      <header class="topbar"><div class="breadcrumb"><span>Workspace</span><span aria-hidden="true">/</span><span>{{ title }}</span></div><button class="primary" @click="showIngest = true"><Plus aria-hidden="true" />Add jobs</button></header>
      <div v-if="notice" role="status" class="workspace-notice"><span>{{ notice }}</span><button class="icon-button" aria-label="Dismiss notification" @click="notice = ''"><X /></button></div>
      <main id="main-content" tabindex="-1" class="page-outlet"><NuxtPage /></main>
      <nav class="mobile-nav" aria-label="Mobile navigation"><NuxtLink v-for="link in links" :key="link.path" :to="link.path" :class="{ active: active(link.path) }" :aria-current="active(link.path) ? 'page' : undefined"><component :is="link.icon" aria-hidden="true" /><span>{{ link.label }}</span></NuxtLink></nav>
    </div>
    <JobIngestModal :show="showIngest" :api-base="apiBase" @close="showIngest = false" @ingested="ingested" />
  </div>
</template>
