<script setup lang="ts">
import { UploadCloud, Mic, Square, FileText, Plus, Check, Download, RefreshCw, ArrowRight, History, X, Save, UserRound } from 'lucide-vue-next'
import { onBeforeRouteLeave } from 'vue-router'
import type { CandidateWorkspace, CandidateProfile, CandidateSource } from '~/types/candidate'
const { apiBase } = useWorkspace()
const workspace = ref<CandidateWorkspace | null>(null), loading = ref(true), error = ref(''), feedback = ref(''), busy = ref('')
const tab = ref('add'), editor = ref<CandidateProfile | null>(null), editorSource = ref<CandidateSource | null>(null), editorBase = ref(''), originalEditor = ref(''), reviewed = ref(false)
const noteTitle = useState('candidate-note-title',()=>''), noteText = useState('candidate-note-text',()=>'')
const transcriptSource = ref<CandidateSource | null>(null), transcriptText = ref(''), cvText = ref(''), cvEditing = ref(false)
const identity = useState('candidate-identity',()=>({name:'Candidate',version_id:''}))
const dirty = computed(() => !!editor.value && JSON.stringify(editor.value)!==originalEditor.value || cvEditing.value && cvText.value!==workspace.value?.master_resume)
const cvInput = ref<HTMLInputElement | null>(null), audioInput = ref<HTMLInputElement | null>(null)
let poll:ReturnType<typeof setInterval>, alive = true
const refresh = async () => {
  try {
    const data = await apiRequest<CandidateWorkspace>(`${apiBase}/api/candidate`)
    if (!alive) return
    workspace.value=data; identity.value={name:data.profile.name,version_id:data.version_id}; error.value=''
  } catch(e:any) { if(alive) error.value=e.message || 'Could not load your profile.' }
  finally { loading.value=false }
}
const perform = async (key:string, work:()=>Promise<void>) => {
  if(busy.value)return
  busy.value=key;error.value='';feedback.value=''
  try { await work() } catch(e:any) { error.value=e.message || 'Could not complete this action.';nextTick(()=>document.querySelector('.candidate-page [role=alert]')?.scrollIntoView({block:'nearest'})) }
  finally { busy.value='' }
}
const upload = (file:File) => perform('upload',async()=>{
  const cv=/\.(pdf|docx)$/i.test(file.name), limit=(cv?10:20)*1024*1024
  if(file.size>limit)throw new Error(`Choose a file smaller than ${cv?10:20} MB.`)
  const form=new FormData();form.append('file',file)
  await apiRequest(`${apiBase}/api/candidate/upload`,{method:'POST',body:form})
  feedback.value=cv?'CV uploaded. Extraction runs in the background.':'Recording uploaded. Your transcript will be ready to review shortly.'
  if(cvInput.value)cvInput.value.value='';if(audioInput.value)audioInput.value.value=''
  await refresh()
})
const fileChanged = (event:Event) => { const file=(event.target as HTMLInputElement).files?.[0];if(file)upload(file) }
const addNote = () => perform('note',async()=>{
  await apiRequest(`${apiBase}/api/candidate/notes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:noteTitle.value.trim(),text:noteText.value.trim()})})
  noteTitle.value='';noteText.value='';feedback.value='Project notes saved. A draft will appear below for review.';await refresh()
})
const openEditor = (profile:CandidateProfile, source:CandidateSource|null=null) => {
  if(dirty.value && !window.confirm('Discard your unsaved profile edits?'))return
  editor.value=JSON.parse(JSON.stringify(profile));editorSource.value=source;editorBase.value=source?.base_version_id || workspace.value!.version_id
  originalEditor.value=JSON.stringify(editor.value);reviewed.value=false;tab.value='profile';error.value=''
  nextTick(()=>document.getElementById('profile-editor-heading')?.focus())
}
const editCurrent = () => { if(workspace.value)openEditor(workspace.value.profile) }
const openTranscript = (source:CandidateSource) => { transcriptSource.value=source;transcriptText.value=source.raw_text;tab.value='add' }
const analyze = (source:CandidateSource,text:string) => perform('analyze',async()=>{
  await apiRequest(`${apiBase}/api/candidate/sources/${source.id}/analyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})})
  transcriptSource.value=null;editor.value=null;editorSource.value=null;feedback.value='Your edited text is being analyzed against the latest profile.';tab.value='add';await refresh()
})
const retry = (source:CandidateSource) => perform('retry',async()=>{
  await apiRequest(`${apiBase}/api/candidate/sources/${source.id}/retry`,{method:'POST'});await refresh()
})
const saveDraft = () => perform('draft',async()=>{
  if(!editorSource.value || !editor.value)return
  await apiRequest(`${apiBase}/api/candidate/sources/${editorSource.value.id}/draft`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:editor.value})})
  originalEditor.value=JSON.stringify(editor.value);feedback.value='Draft saved. It will not be used for applications until you approve it.';await refresh()
})
const approve = () => perform('approve',async()=>{
  if(!editor.value || !reviewed.value)return
  await apiRequest(`${apiBase}/api/candidate/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version_id:editorBase.value,source_id:editorSource.value?.id,profile:editor.value})})
  originalEditor.value=JSON.stringify(editor.value);editor.value=null;editorSource.value=null
  await refresh();feedback.value='Profile approved. Your master CV is ready, and new applications will use this version.';tab.value='cv';nextTick(()=>document.querySelector('.candidate-page')?.scrollTo({top:0}))
})
const saveCV = () => perform('cv',async()=>{
  if(!workspace.value)return
  await apiRequest(`${apiBase}/api/candidate/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version_id:workspace.value.version_id,profile:workspace.value.profile,master_resume:cvText.value})})
  cvEditing.value=false;await refresh();feedback.value='Master CV saved as a new version.'
})
const viewVersion = (id:string) => perform('version',async()=>{
  const data=await apiRequest<{profile:CandidateProfile}>(`${apiBase}/api/candidate/versions/${id}`)
  openEditor(data.profile);feedback.value='Historical profile loaded as a draft. Approval creates a new version; previous versions remain saved.'
})
const date = (value:string) => new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'})
const retryAvailable = (source:CandidateSource) => source.status==='failed' || ['queued','processing'].includes(source.status) && Date.now()-new Date(source.updated_at).getTime()>600000
const sourceLabel:Record<string,string>={queued:'Waiting to process',processing:'Processing…',transcribed:'Transcript ready',ready:'Ready to review',approved:'Approved',failed:'Needs attention'}
const recording = ref(false), clipUrl = ref(''), clip = ref<Blob|null>(null), seconds=ref(0)
let recorder:MediaRecorder|null=null, stream:MediaStream|null=null, recordTimer:ReturnType<typeof setInterval>|undefined
const stopRecording = () => { if(recorder?.state==='recording')recorder.stop();stream?.getTracks().forEach(track=>track.stop());if(recordTimer)clearInterval(recordTimer);recording.value=false }
const discardClip = () => { if(clipUrl.value)URL.revokeObjectURL(clipUrl.value);clipUrl.value='';clip.value=null }
const startRecording = async () => {
  error.value=''
  try {
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)throw new Error('Recording is unavailable in this browser. Upload an audio file or type your explanation instead.')
    stream=await navigator.mediaDevices.getUserMedia({audio:true});discardClip()
    const type=['audio/webm','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type))
    recorder=type?new MediaRecorder(stream,{mimeType:type}):new MediaRecorder(stream)
    const chunks:BlobPart[]=[]
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)}
    recorder.onstop=()=>{if(!alive)return;clip.value=new Blob(chunks,{type:recorder?.mimeType||'audio/webm'});clipUrl.value=URL.createObjectURL(clip.value)}
    recorder.start();recording.value=true;seconds.value=0
    recordTimer=setInterval(()=>{seconds.value++;if(seconds.value>=180)stopRecording()},1000)
  } catch(e:any) {stream?.getTracks().forEach(track=>track.stop());error.value=e.name==='NotAllowedError'?'Microphone permission was declined. You can upload audio or type your project notes.':e.message}
}
const sendClip = async () => {
  if(!clip.value)return
  const suffix=clip.value.type.includes('mp4')?'m4a':clip.value.type.includes('ogg')?'ogg':'webm'
  await upload(new File([clip.value],`Project explanation.${suffix}`,{type:clip.value.type}))
  if(!error.value)discardClip()
}
const guard = (event:BeforeUnloadEvent) => {if(dirty.value || recording.value || clip.value){event.preventDefault();event.returnValue=''}}
onBeforeRouteLeave(()=> {if((dirty.value||recording.value||clip.value)&&!window.confirm('Leave with unsaved changes or a project recording?'))return false;stopRecording()})
onMounted(()=>{refresh();poll=setInterval(()=>{if(workspace.value?.sources.some(s=>['queued','processing'].includes(s.status))&&!document.hidden)refresh()},3000);window.addEventListener('beforeunload',guard)})
onUnmounted(()=>{alive=false;clearInterval(poll);stopRecording();discardClip();window.removeEventListener('beforeunload',guard)})
</script>

<template>
  <section class="candidate-page" aria-labelledby="candidate-heading">
    <div class="candidate-page-heading"><div><p class="profile-eyebrow">YOUR EXPERIENCE, IN YOUR WORDS</p><h1 id="candidate-heading">My Profile</h1><p class="muted">Bring your CV and project stories together. Review the facts, then build your next application.</p></div><button class="secondary" :disabled="!!busy || loading" @click="refresh"><RefreshCw aria-hidden="true" />Refresh</button></div>
    <div v-if="error" role="alert" class="feedback-error">{{ error }}</div><div v-if="feedback" role="status" class="workspace-notice">{{ feedback }}</div>
    <p v-if="loading" role="status" class="empty">Loading your profile…</p>
    <template v-else-if="workspace">
      <div class="profile-overview"><div class="profile-avatar"><UserRound aria-hidden="true" /></div><div><strong>{{ workspace.profile.name }}</strong><span>{{ workspace.profile.headline || 'Your approved candidate profile' }}</span></div><span class="profile-version">{{ workspace.profile.experience.length }} experiences · {{ workspace.profile.projects.length }} projects</span></div>
      <nav class="profile-tabs" aria-label="Candidate profile sections"><button v-for="item in [{id:'add',label:'Add information',icon:Plus},{id:'profile',label:'Review profile',icon:UserRound},{id:'cv',label:'Master CV',icon:FileText},{id:'history',label:'Version history',icon:History}]" :key="item.id" :aria-pressed="tab===item.id" :class="{active:tab===item.id}" @click="tab=item.id;if(item.id==='profile'&&!editor)editCurrent()"><component :is="item.icon" aria-hidden="true" />{{ item.label }}</button></nav>
      <div v-show="tab==='add'">
        <div class="candidate-input-grid">
          <section class="candidate-card"><span class="profile-step">01 / YOUR STARTING POINT</span><UploadCloud class="candidate-card-icon" aria-hidden="true" /><h2>Bring your existing CV</h2><p>Upload your CV to create a profile draft. You’ll review it before replacing your current profile.</p><input ref="cvInput" type="file" accept=".pdf,.docx" class="hidden" :disabled="!!busy" aria-label="Upload candidate CV" @change="fileChanged"><button class="secondary" :disabled="!!busy" @click="cvInput?.click()"><UploadCloud aria-hidden="true" />{{ busy==='upload'?'Uploading…':'Choose your CV' }}</button><small>PDF or DOCX · up to 10 MB · selectable text</small><p v-if="!workspace.capabilities.extraction" class="profile-hint">Automatic extraction isn’t configured. You can still upload a CV, read its text, and enter your profile manually.</p></section>
          <section class="candidate-card"><span class="profile-step">02 / THE WORK BEHIND THE CV</span><h2>Tell a project story</h2><p>What did you build, what was your role, and what changed because of your work?</p><label class="profile-field">Project name<input v-model="noteTitle" maxlength="300" placeholder="e.g. A logistics platform"></label><label class="profile-field">Your explanation<textarea v-model="noteText" rows="5" maxlength="40000" placeholder="Describe the problem, your contribution, technologies, and results. It’s fine if you don’t have exact numbers." /></label><button class="primary" :disabled="!!busy || !noteTitle.trim() || noteText.trim().length<20" @click="addNote"><ArrowRight aria-hidden="true" />{{ busy==='note'?'Saving…':'Create a project draft' }}</button><small>At least 20 characters. Notes stay available while you move around the workspace.</small></section>
        </div>
        <section class="candidate-card voice-card"><div><span class="profile-step">PREFER TO TALK IT THROUGH?</span><h2>Explain it in your own voice</h2><p>Record up to 3 minutes or upload audio. Review and correct the transcript before extracting project facts.</p><p v-if="!workspace.capabilities.voice" class="profile-hint">Voice transcription isn’t configured for this workspace. You can use text notes above.</p></div><div class="voice-controls"><button v-if="!recording" class="secondary" :disabled="!!busy || !workspace.capabilities.voice" @click="startRecording"><Mic aria-hidden="true" />Record explanation</button><button v-else class="secondary recording-button" @click="stopRecording"><Square aria-hidden="true" />Stop · {{ seconds }}s</button><input ref="audioInput" type="file" accept=".mp3,.mp4,.m4a,.wav,.webm,.ogg" class="hidden" :disabled="!!busy || !workspace.capabilities.voice" aria-label="Upload project recording" @change="fileChanged"><button class="subtle" :disabled="!!busy || recording || !workspace.capabilities.voice" @click="audioInput?.click()">Upload audio · max 20 MB</button><template v-if="clipUrl"><audio :src="clipUrl" controls aria-label="Recorded project explanation" /><button class="primary" :disabled="!!busy" @click="sendClip">Transcribe recording</button><button class="subtle" :disabled="!!busy" @click="discardClip">Discard recording</button></template></div></section>
        <section v-if="transcriptSource" class="candidate-card transcript-review"><h2>{{ transcriptSource.kind==='voice' ? 'Review your transcript' : 'Review your source text' }}</h2><p>Correct names, dates, numbers, and technical terms. Changes here become the source for the next draft.</p><label class="profile-field">{{ transcriptSource.title }}<textarea v-model="transcriptText" rows="9" maxlength="60000" /></label><div class="profile-inline-actions"><button class="secondary" :disabled="!!busy" @click="transcriptSource=null">Close</button><button class="primary" :disabled="!!busy || transcriptText.trim().length<20" @click="analyze(transcriptSource,transcriptText)">Use this text to create a draft</button></div></section>
        <section class="profile-sources"><div class="profile-section-heading"><h2>Source library</h2><span class="muted">Uploads, notes & recordings</span></div><p v-if="!workspace.sources.length" class="profile-empty">Start with a CV or a project story. Your original text and review drafts will appear here.</p><article v-for="source in workspace.sources" :key="source.id" class="source-item"><div class="source-item-copy"><strong>{{ source.title }}</strong><small>{{ source.kind==='resume'?'CV upload':source.kind==='voice'?'Voice note':'Project notes' }} · {{ date(source.created_at) }}</small><span class="source-status" :class="source.status">{{ sourceLabel[source.status] || source.status }}</span><p v-if="source.error" class="feedback-error">{{ source.error }}</p></div><div class="source-item-actions"><button v-if="source.status==='ready' && source.proposal" class="secondary" :disabled="!!busy" @click="openEditor(source.proposal!.profile,source)">Review draft<ArrowRight aria-hidden="true" /></button><button v-if="['transcribed','failed'].includes(source.status)" class="secondary" :disabled="!!busy" @click="openTranscript(source)">{{ source.raw_text ? 'Review source text' : 'Paste source text' }}</button><button v-if="retryAvailable(source)" class="subtle" :disabled="!!busy" @click="retry(source)">Retry processing</button><details v-if="source.raw_text"><summary>Original text</summary><pre>{{ source.raw_text }}</pre></details></div></article></section>
      </div>
      <section v-show="tab==='profile'" class="profile-review">
        <template v-if="editor"><div class="profile-section-heading"><div><span class="profile-step">{{ editorSource?'REVIEW A PROPOSED UPDATE':'EDIT YOUR PROFILE' }}</span><h2 id="profile-editor-heading" tabindex="-1">{{ editorSource?.title || 'Your confirmed experience' }}</h2></div><button class="subtle" :disabled="!!busy" @click="editCurrent">Load active profile</button></div>
          <div v-if="editorSource" class="profile-comparison"><div><small>ACTIVE PROFILE</small><strong>{{ workspace.profile.name }}</strong><span>{{ workspace.profile.experience.length }} experiences · {{ workspace.profile.projects.length }} projects</span></div><ArrowRight aria-hidden="true" /><div><small>YOUR DRAFT</small><strong>{{ editor.name || 'Name needed' }}</strong><span>{{ editor.experience.length }} experiences · {{ editor.projects.length }} projects</span></div></div>
          <div v-if="editorSource?.base_version_id!==workspace.version_id && editorSource" role="alert" class="feedback-error">Your active profile has changed since this draft was created. Re-analyze the source before approving.<button class="secondary" :disabled="!!busy" @click="analyze(editorSource,editorSource.raw_text)">Re-analyze against current profile</button></div>
          <div v-if="editorSource?.proposal?.warnings.length" class="profile-callout"><strong>Check before approving</strong><ul><li v-for="warning in editorSource.proposal.warnings" :key="warning">{{ warning }}</li></ul></div>
          <div v-if="editorSource?.proposal?.questions.length" class="profile-callout"><strong>A few details would strengthen this profile</strong><ul><li v-for="question in editorSource.proposal.questions" :key="question">{{ question }}</li></ul><p>Add what you know to the relevant project fields below. Unknown details can stay blank.</p></div>
          <details v-if="editorSource?.raw_text" class="profile-source-text"><summary>Read the original source alongside your draft</summary><pre>{{ editorSource.raw_text }}</pre></details>
          <CandidateProfileEditor v-model="editor" />
          <div class="profile-approval"><label class="profile-check"><input v-model="reviewed" type="checkbox">I reviewed the facts, dates, and metrics in this profile.</label><p>Approval creates a new version and builds your master CV from these facts. Existing application documents stay unchanged.</p><div class="profile-inline-actions"><button v-if="editorSource" class="secondary" :disabled="!!busy" @click="saveDraft"><Save aria-hidden="true" />Save draft</button><button class="primary" :disabled="!!busy || !reviewed || !editor.name.trim() || editorBase!==workspace.version_id" @click="approve"><Check aria-hidden="true" />{{ busy==='approve'?'Saving…':'Approve profile & build CV' }}</button></div></div>
        </template><p v-else class="profile-empty">Choose a source draft to review, or <button class="text-link" @click="editCurrent">edit your active profile</button>.</p>
      </section>
      <section v-show="tab==='cv'" class="profile-cv"><div class="profile-section-heading"><div><h2>Your master CV</h2><p class="muted">Built from your approved profile. New job applications use this version as their starting point.</p></div><div class="profile-inline-actions"><button v-if="!cvEditing" class="secondary" @click="cvText=workspace.master_resume;cvEditing=true">Edit CV text</button><a :href="`${apiBase}/api/candidate/cv/pdf`" class="secondary button-link" target="_blank" rel="noopener noreferrer"><Download aria-hidden="true" />Download PDF</a></div></div><template v-if="cvEditing"><label class="profile-field">Master CV text<textarea v-model="cvText" rows="25" maxlength="60000" /></label><p class="profile-hint">Keep edits factual. For facts you also want reflected in other application answers, update the profile fields too.</p><div class="profile-inline-actions"><button class="secondary" :disabled="!!busy" @click="cvEditing=false">Cancel</button><button class="primary" :disabled="!!busy || cvText.trim().length<20" @click="saveCV">Approve CV edits</button></div></template><article v-else class="paper profile-cv-paper"><MarkdownText :text="workspace.master_resume" /></article></section>
      <section v-show="tab==='history'" class="candidate-card"><h2>Approved versions</h2><p>Each approval preserves a snapshot. Load a previous profile as a draft to bring information back without overwriting history.</p><article v-for="version in workspace.versions" :key="version.id" class="source-item"><div><strong>{{ version.name }}</strong><small>{{ date(version.created_at) }}{{ version.id===workspace.version_id?' · Active version':'' }}</small></div><button class="secondary" :disabled="!!busy" @click="viewVersion(version.id)">Load as draft</button></article></section>
    </template>
  </section>
</template>
