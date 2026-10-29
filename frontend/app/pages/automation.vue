<script setup lang="ts">
import { RefreshCw, Globe, MessagesSquare, FileText } from 'lucide-vue-next'
const { apiBase, counts, refreshMetrics, jobsChanged, notice } = useWorkspace()
const busy = ref(''), error = ref('')
const actions = [
 {id:'ats',title:'Company career pages',description:'Find roles on Greenhouse, Lever, and Ashby.',detail:'The scheduled search runs every six hours.',icon:Globe,endpoint:'/api/metrics/scrapers/trigger?mode=ats_only'},
 {id:'community',title:'Community hiring posts',description:'Search Hacker News and Reddit for direct hiring opportunities.',detail:'Reddit runs every 20 minutes; Hacker News runs hourly.',icon:MessagesSquare,endpoint:'/api/metrics/scrapers/trigger-community'},
 {id:'tailor',title:'Application tailoring',description:'Prepare fit assessments, cover letters, resumes, and answers.',detail:'Queue up to 50 pending roles using your saved profile.',icon:FileText,endpoint:'/api/jobs/tailor-pending?limit=50'}
]
const trigger = async (action:typeof actions[number])=>{
 if(busy.value)return
 busy.value=action.id;error.value=''
 try{const data=await apiRequest(`${apiBase}${action.endpoint}`,{method:'POST'});notice.value=data.message || 'Task queued. New results will appear as they are processed.';jobsChanged()}
 catch(err:any){error.value=err.message||'Could not start this task.'}
 finally{busy.value=''}
}
</script>
<template><section class="auxiliary active"><div class="automation-heading"><div><h1>Automation</h1><p class="muted">Find opportunities while you focus on applying.</p></div><button class="secondary" @click="refreshMetrics"><RefreshCw aria-hidden="true" />Refresh status</button></div><p v-if="error" role="alert" class="feedback-error">{{ error }}</p><div class="automation-summary"><span>{{ counts ? counts.queued_for_llm.toLocaleString() : '—' }} roles preparing</span><span>{{ counts ? counts.ready_to_apply.toLocaleString() : '—' }} ready to review</span></div><div class="aux-panel"><section v-for="action in actions" :key="action.id" class="aux-row"><component :is="action.icon" aria-hidden="true" /><div class="automation-copy"><h2>{{ action.title }}</h2><p>{{ action.description }}</p><small>{{ action.detail }}</small></div><button class="secondary" :disabled="!!busy" @click="trigger(action)"><RefreshCw v-if="busy===action.id" class="animate-spin" aria-hidden="true" />{{ busy===action.id ? 'Queuing…' : 'Run now' }}</button></section></div><p class="automation-note">Tasks run in the background. Queuing a search does not mean it has finished. Use Opportunities to review newly discovered roles.</p></section></template>
