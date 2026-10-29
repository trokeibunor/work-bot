<script setup lang="ts">
import { ArrowLeft, ExternalLink, Check, EyeOff, RotateCcw, X, PanelRight, RefreshCw } from 'lucide-vue-next'
import type { Job } from '~/types/jobs'
import { jobTitle, jobLocation, listingUrl } from '~/types/jobs'
const route = useRoute(), router = useRouter()
const { apiBase, jobsChanged } = useWorkspace()
const jobId = computed(() => route.params.id as string)
const queueLocation = computed(() => { const { from, ...query } = route.query; return { path:from==='applications' ? '/applications' : '/',query } })
const job = ref<Job | null>(null), loading = ref(true), loadError = ref(''), actionError = ref('')
const busy = ref(''), ignoredStatus = ref<string | null>(null), editorRef = ref<{ unsaved: boolean } | null>(null)
const roleDialog = ref<HTMLDialogElement | null>(null)
let controller: AbortController | undefined
const fetchJob = async (silent = false) => {
  controller?.abort(); const request = new AbortController(); controller = request
  if (!silent) loading.value = true
  loadError.value = ''
  try {
    const data = await apiRequest<Job>(`${apiBase}/api/jobs/${jobId.value}`,{signal:request.signal})
    if (!request.signal.aborted) job.value = data
  } catch (err: any) { if (err.name!=='AbortError') { if(silent) actionError.value=err.message;else loadError.value=err.message || 'Could not load this application.' } }
  finally { if(controller===request) loading.value=false }
}
const nextJob = async () => {
  const params = new URLSearchParams()
  for(const [key,value] of Object.entries(route.query)) if(typeof value==='string' && ['source','search','min_score','days','founder_led_only','sort_by','organization_type'].includes(key))params.set(key,value)
  // Continue through remaining ready roles after saving an application.
  params.set('status','ready_to_apply');params.set('paginate','true');params.set('limit','1')
  const data = await apiRequest<{items:Job[]}>(`${apiBase}/api/jobs?${params}`)
  const next = data.items.find(item=>item.id!==jobId.value)
  await router.push(next ? {path:`/execute/${next.id}`,query:{...route.query,selected:next.id}} : queueLocation.value)
}
const updateStatus = async (action:'apply'|'ignore'|'restore') => {
  if(!job.value||busy.value)return
  if(editorRef.value?.unsaved){actionError.value='Save or cancel your document edits before changing this application.';return}
  busy.value=action;actionError.value=''
  const previous=job.value.status
  try {
    const endpoint=action==='apply' ? 'status' : action==='ignore' ? 'ignore' : ignoredStatus.value ? 'status' : 'unignore'
    const updated=await apiRequest<Job>(`${apiBase}/api/jobs/${jobId.value}/${endpoint}`,{
      method:'POST',headers:{'Content-Type':'application/json'},...(endpoint==='status'?{body:JSON.stringify({status:action==='apply'?'applied':ignoredStatus.value})}:{})
    })
    job.value.status=updated.status
    if(action==='ignore')ignoredStatus.value=previous
    if(action==='restore')ignoredStatus.value=null
    jobsChanged()
    if(action==='apply')try{await nextJob()}catch{actionError.value='Application saved. Could not load the next role; return to opportunities to continue.'}
  }catch(err:any){actionError.value=err.message||'Could not save your changes.'}
  finally{busy.value=''}
}
const tailor = async () => {
  if(busy.value)return
  busy.value='tailor';actionError.value=''
  try{await apiRequest(`${apiBase}/api/jobs/${jobId.value}/tailor`,{method:'POST'});await fetchJob(true);jobsChanged()}
  catch(err:any){actionError.value=err.message||'Could not generate application materials.'}
  finally{busy.value=''}
}
const keydown=(event:KeyboardEvent)=>{
  if(document.querySelector('dialog[open]')||(event.target as HTMLElement)?.closest('input,textarea,select,button,a,[contenteditable=true]'))return
  if((event.metaKey||event.ctrlKey)&&event.key==='Enter'&&job.value?.status!=='applied'){event.preventDefault();updateStatus('apply')}
  if(event.key==='Escape')router.push(queueLocation.value)
}
watch(jobId,()=>{ignoredStatus.value=null;actionError.value='';job.value=null;fetchJob()})
onMounted(()=>{fetchJob();window.addEventListener('keydown',keydown)})
onUnmounted(()=>{controller?.abort();window.removeEventListener('keydown',keydown)})
</script>
<template>
  <section class="workspace active" aria-label="Prepare application">
    <div v-if="loading" role="status" class="empty">Loading application…</div>
    <div v-else-if="loadError" role="alert" class="empty"><h1>Could not load this application</h1><p>{{ loadError }}</p><button class="secondary" @click="fetchJob()">Retry</button><NuxtLink :to="queueLocation" class="text-link inline-link">Back to opportunities</NuxtLink></div>
    <template v-else-if="job">
      <header class="workspace-heading"><div><NuxtLink :to="queueLocation" class="text-link inline-link"><ArrowLeft aria-hidden="true" />{{ route.query.from==='applications' ? 'Back to applications' : 'Back to opportunities' }}</NuxtLink><h1>{{ jobTitle(job) }}</h1><p>{{ job.company_name }} · {{ jobLocation(job) }}</p></div><div class="workspace-actions"><button class="secondary role-details-button" aria-label="Role details" @click="roleDialog?.showModal()"><PanelRight aria-hidden="true" /><span>Role details</span></button><a v-if="listingUrl(job.source_url)" :href="listingUrl(job.source_url)" target="_blank" rel="noopener noreferrer" class="secondary button-link" aria-label="View original listing"><ExternalLink aria-hidden="true" /><span>View listing</span></a></div></header>
      <p v-if="actionError" role="alert" class="feedback-error">{{ actionError }}</p>
      <div v-if="ignoredStatus" role="status" class="workspace-notice"><span>Job ignored.</span><button :disabled="!!busy" @click="updateStatus('restore')">Undo</button></div>
      <div class="workspace-body">
        <AssetCopier v-if="job.assets" ref="editorRef" :key="job.id" :job-id="job.id" :assets="job.assets" :hiring-contacts="job.hiring_contacts" :company-name="job.company_name" :job-title="job.job_title" :source="job.source" :source-url="job.source_url" :is-founder-led="job.is_founder_led" @updated="fetchJob(true)" />
        <div v-else class="empty"><h2>{{ job.status==='queued_for_llm' ? 'Your materials are being prepared' : 'No application materials yet' }}</h2><p>Review the role, then generate a tailored draft using your saved profile.</p><button class="primary" :disabled="!!busy" @click="tailor"><RefreshCw :class="{'animate-spin':busy==='tailor'}" />{{ busy==='tailor' ? 'Preparing materials…' : 'Generate materials' }}</button><button class="secondary" :disabled="!!busy" @click="fetchJob(true)">Check for updates</button></div>
        <aside class="context" aria-label="Role context" tabindex="0"><div class="company-logo" aria-hidden="true">{{ job.company_name?.[0] || '?' }}</div><h2>{{ job.company_name }}</h2><p>{{ jobLocation(job) }}</p><section class="context-section"><h3>Fit assessment</h3><p>{{ job.match_reasoning || 'No assessment is available yet.' }}</p></section><section v-if="job.tech_stack_tags?.length" class="context-section"><h3>Technologies mentioned</h3><div class="tags"><span v-for="tag in job.tech_stack_tags" :key="tag" class="tag">{{ tag }}</span></div></section><section class="context-section"><h3>Before you apply</h3><p>Confirm location and working-hour requirements in the original listing. Review all generated claims before sending.</p></section><button class="text-link" @click="roleDialog?.showModal()">Read full job description<ExternalLink aria-hidden="true" /></button></aside>
      </div>
      <footer class="workspace-footer"><span class="footer-copy">Apply on the company's site, then mark it here.</span><div class="footer-actions"><button v-if="job.status==='archived'" class="subtle" :disabled="!!busy" @click="updateStatus('restore')"><RotateCcw aria-hidden="true" />Restore job</button><button v-else class="subtle" :disabled="!!busy" @click="updateStatus('ignore')"><EyeOff aria-hidden="true" />Ignore job</button><button class="primary" :disabled="!!busy || job.status==='applied'" @click="updateStatus('apply')"><Check aria-hidden="true" />{{ busy==='apply' ? 'Saving…' : job.status==='applied' ? 'Applied' : 'Mark applied & next' }}</button></div></footer>
      <dialog ref="roleDialog" class="role-dialog" aria-label="Role details"><button class="icon-button close-role-dialog" aria-label="Close role details" @click="roleDialog?.close()"><X /></button><div class="detail-scroll" tabindex="0"><JobPreview :job="job" /></div></dialog>
    </template>
  </section>
</template>
