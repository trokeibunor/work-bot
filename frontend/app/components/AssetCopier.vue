<script setup lang="ts">
import { ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import {
  Copy, Check, Sparkles, Send, FileText, HelpCircle,
  MessageSquare, Mail, Edit3, Save, RefreshCw, Download,
  ExternalLink, UserCheck, ShieldCheck, CheckCircle2, AlertCircle,
  Briefcase, Rocket, Globe
} from 'lucide-vue-next'

interface AssetData {
  id: string
  candidate_snapshot?: {data:{name:string},version_id:string}
  cover_letter_markdown: string
  cover_letter_pdf_path?: string
  resume_markdown: string
  resume_pdf_path?: string
  ans_why_company_250: string
  ans_why_company_500: string
  ans_technical_challenge_250: string
  ans_technical_challenge_500: string
  ans_python_go_proficiency_220: string
  ans_location_relocation_220: string
  custom_qa?: Record<string, string>
}

interface HiringContacts {
  primary_email?: string
  is_direct_listing_email: boolean
  direct_emails: string[]
  derived_inboxes: string[]
  mailto_url?: string
}

const props = defineProps<{
  jobId: string
  assets: AssetData
  hiringContacts?: HiringContacts
  companyName?: string
  jobTitle?: string
  source?: string
  sourceUrl?: string
  isFounderLed?: boolean
}>()

const emit = defineEmits(['updated'])

const config = useRuntimeConfig()
const apiBase = config.public.apiBase ?? 'http://localhost:8000'

// Active Tab
const activeTab = ref<'answers' | 'cover_letter' | 'resume' | 'contacts' | 'adhoc'>('cover_letter')

// Copy state tracking
const copiedField = ref<string | null>(null)
const copyError = ref('')

const copyToClipboard = async (text: string, fieldKey: string) => {
  copyError.value = ''
  try {
    await navigator.clipboard.writeText(text)
    copiedField.value = fieldKey
    setTimeout(() => {
      if (copiedField.value === fieldKey) {
        copiedField.value = null
      }
    }, 2000)
  } catch (err) {
    copyError.value = 'Could not copy. Please select the text and copy it manually.'
  }
}

// ----------------------------------------------------------------------
// COVER LETTER CUSTOMIZATION STATE & METHODS
// ----------------------------------------------------------------------
const roleArchetypes = [
  { value: 'auto', label: 'Auto-Detect Role', desc: 'Infers archetype automatically from job title and stack' },
  { value: 'backend_systems', label: 'Backend & Systems Depth', desc: 'Focuses on Golang/Python, high concurrency, and distributed resilience' },
  { value: 'frontend_fullstack', label: 'Frontend & Full-Stack', desc: 'Focuses on Vue/Nuxt, performance, fraud UI, and responsive systems' },
  { value: 'devops_cloud', label: 'DevOps & Cloud Infra', desc: 'Focuses on Linux, Docker, AWS/GCP, and CI/CD automation' },
  { value: 'ai_data', label: 'AI/ML & Data Engineering', desc: 'Focuses on NILM heuristics, LLM workflows, and data pipelines' },
  { value: 'leadership', label: 'Engineering Leadership', desc: 'Focuses on project lead engineering, system architecture, and mentoring' }
]

const selectedArchetype = ref<string>('auto')
const candidateDirectives = ref<string>('')
const isRegeneratingLetter = ref<boolean>(false)
const isEditingLetter = ref<boolean>(false)
const editableLetterMarkdown = ref<string>(props.assets.cover_letter_markdown || '')
const isSavingLetter = ref<boolean>(false)
const letterSavedSuccess = ref<boolean>(false)
const letterError = ref<string>('')

// Keep editable letter markdown synced if prop updates externally
watch(() => props.assets.cover_letter_markdown, (newVal) => {
  if (!isEditingLetter.value && newVal) {
    editableLetterMarkdown.value = newVal
  }
})

const regenerateCoverLetter = async () => {
  if (isRegeneratingLetter.value) return
  isRegeneratingLetter.value = true
  letterError.value = ''
  letterSavedSuccess.value = false

  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/regenerate-cover-letter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        archetype: selectedArchetype.value,
        custom_instructions: candidateDirectives.value.trim() || null
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to regenerate (${res.status})`)
    }

    const data = await res.json()
    editableLetterMarkdown.value = data.assets.cover_letter_markdown
    letterSavedSuccess.value = true
    setTimeout(() => { letterSavedSuccess.value = false }, 3000)
    emit('updated')
  } catch (err: any) {
    letterError.value = err.message || 'Error regenerating cover letter'
  } finally {
    isRegeneratingLetter.value = false
  }
}

const saveEditedCoverLetter = async () => {
  if (isSavingLetter.value || !editableLetterMarkdown.value.trim()) return
  isSavingLetter.value = true
  letterError.value = ''
  letterSavedSuccess.value = false

  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/cover-letter`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cover_letter_markdown: editableLetterMarkdown.value.trim()
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to save cover letter (${res.status})`)
    }

    const data = await res.json()
    isEditingLetter.value = false
    letterSavedSuccess.value = true
    setTimeout(() => { letterSavedSuccess.value = false }, 3000)
    emit('updated')
  } catch (err: any) {
    letterError.value = err.message || 'Error saving cover letter'
  } finally {
    isSavingLetter.value = false
  }
}

const cancelEditLetter = () => {
  editableLetterMarkdown.value = props.assets.cover_letter_markdown || ''
  isEditingLetter.value = false
  letterError.value = ''
}

const downloadPdf = () => {
  window.open(`${apiBase}/api/assets/${props.jobId}/pdf`, '_blank')
}

// ----------------------------------------------------------------------
// RESUME CUSTOMIZATION STATE & METHODS
// ----------------------------------------------------------------------
const isRegeneratingResume = ref<boolean>(false)
const isEditingResume = ref<boolean>(false)
const editableResumeMarkdown = ref<string>(props.assets.resume_markdown || '')
const isSavingResume = ref<boolean>(false)
const resumeSavedSuccess = ref<boolean>(false)
const resumeError = ref<string>('')
const resumeDirectives = ref<string>('')

watch(() => props.assets.resume_markdown, (newVal) => {
  if (!isEditingResume.value && newVal) {
    editableResumeMarkdown.value = newVal
  }
})

const regenerateResume = async () => {
  if (isRegeneratingResume.value) return
  isRegeneratingResume.value = true
  resumeError.value = ''
  resumeSavedSuccess.value = false

  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/regenerate-resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        custom_instructions: resumeDirectives.value.trim() || null
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to regenerate resume (${res.status})`)
    }

    const data = await res.json()
    editableResumeMarkdown.value = data.assets.resume_markdown
    resumeSavedSuccess.value = true
    setTimeout(() => { resumeSavedSuccess.value = false }, 3000)
    emit('updated')
  } catch (err: any) {
    resumeError.value = err.message || 'Error regenerating resume'
  } finally {
    isRegeneratingResume.value = false
  }
}

const saveEditedResume = async () => {
  if (isSavingResume.value || !editableResumeMarkdown.value.trim()) return
  isSavingResume.value = true
  resumeError.value = ''
  resumeSavedSuccess.value = false

  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/resume`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_markdown: editableResumeMarkdown.value.trim()
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to save resume (${res.status})`)
    }

    const data = await res.json()
    isEditingResume.value = false
    resumeSavedSuccess.value = true
    setTimeout(() => { resumeSavedSuccess.value = false }, 3000)
    emit('updated')
  } catch (err: any) {
    resumeError.value = err.message || 'Error saving resume'
  } finally {
    isSavingResume.value = false
  }
}

const cancelEditResume = () => {
  editableResumeMarkdown.value = props.assets.resume_markdown || ''
  isEditingResume.value = false
  resumeError.value = ''
}

const downloadResumePdf = () => {
  window.open(`${apiBase}/api/assets/${props.jobId}/resume/pdf`, '_blank')
}

// ----------------------------------------------------------------------
// AD-HOC COPILOT
// ----------------------------------------------------------------------
const customQuestion = ref('')
const customMaxChars = ref(220)
const isGenerating = ref(false)
const adHocAnswer = ref('')
const adHocError = ref('')

const generateAdHocAnswer = async () => {
  if (!customQuestion.value.trim() || isGenerating.value) return
  isGenerating.value = true
  adHocError.value = ''
  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/custom-question`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: customQuestion.value,
        max_chars: customMaxChars.value
      })
    })
    if (!res.ok) throw new Error('Failed to generate answer')
    const data = await res.json()
    adHocAnswer.value = data.answer
  } catch (err: any) {
    adHocError.value = err.message || 'Generation error'
  } finally {
    isGenerating.value = false
  }
}

// ----------------------------------------------------------------------
// FOLLOW-UP MESSAGE BUILDER FOR HIRING CONTACTS
// ----------------------------------------------------------------------
const isCommunityOrFounder = computed(() => {
  return props.isFounderLed || props.source === 'reddit' || props.source === 'hackernews'
})

const getDirectCommunityPlatform = () => {
  if (props.source === 'reddit') return 'Reddit'
  if (props.source === 'hackernews') return 'Hacker News'
  return 'community channels'
}

const outreachPersona = ref('technical_lead')
const outreachType = ref('post_application')
const isGeneratingOutreach = ref(false)
const outreachError = ref('')
const outreachSubjects = ref<string[]>([])
const followUpPitchMessage = ref('')

const generateOutreach = async () => {
  if (isGeneratingOutreach.value) return
  isGeneratingOutreach.value = true
  outreachError.value = ''
  outreachSubjects.value = []
  
  try {
    const res = await fetch(`${apiBase}/api/jobs/${props.jobId}/outreach`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipient_persona: outreachPersona.value,
        outreach_type: outreachType.value
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to generate outreach (${res.status})`)
    }

    const data = await res.json()
    followUpPitchMessage.value = data.body
    outreachSubjects.value = [data.subject_1, data.subject_2]
  } catch (err: any) {
    outreachError.value = err.message || 'Error generating outreach'
  } finally {
    isGeneratingOutreach.value = false
  }
}
const documentTab = computed(() => activeTab.value === 'cover_letter' || activeTab.value === 'resume')
const resumeTab = computed(() => activeTab.value === 'resume')
const editing = computed(() => resumeTab.value ? isEditingResume.value : isEditingLetter.value)
const saving = computed(() => resumeTab.value ? isSavingResume.value : isSavingLetter.value)
const regenerating = computed(() => resumeTab.value ? isRegeneratingResume.value : isRegeneratingLetter.value)
const documentError = computed(() => resumeTab.value ? resumeError.value : letterError.value)
const documentSaved = computed(() => resumeTab.value ? resumeSavedSuccess.value : letterSavedSuccess.value)
const documentText = computed(() => resumeTab.value ? props.assets.resume_markdown || '' : props.assets.cover_letter_markdown || '')
const documentTitle = computed(() => resumeTab.value ? 'Resume' : 'Cover letter')
const unsaved = computed(() => (isEditingLetter.value && editableLetterMarkdown.value !== props.assets.cover_letter_markdown) || (isEditingResume.value && editableResumeMarkdown.value !== (props.assets.resume_markdown || '')))
onBeforeRouteLeave(() => !unsaved.value || window.confirm('Leave this application and discard your unsaved edits?'))
const answers = computed(() => [
  { label: 'Why this company?', variants: [{text: props.assets.ans_why_company_250, max:250}, {text: props.assets.ans_why_company_500,max:500}] },
  { label: 'A technical challenge', variants: [{text: props.assets.ans_technical_challenge_250,max:250},{text:props.assets.ans_technical_challenge_500,max:500}] },
  { label: 'Python and Go experience',variants:[{text:props.assets.ans_python_go_proficiency_220,max:220}] },
  { label: 'Location and relocation',variants:[{text:props.assets.ans_location_relocation_220,max:220}] },
  ...Object.entries(props.assets.custom_qa || {}).map(([label,text])=>({label,variants:[{text,max:0}]}))
])
const answerVersions = ref<Record<number,number>>({})
const answerVariant = (index: number) => answers.value[index].variants[answerVersions.value[index] || 0]
const materialTabs = [{value:'cover_letter',label:'Cover letter'},{value:'resume',label:'Resume'},{value:'answers',label:'Answers'},{value:'contacts',label:'Outreach'},{value:'adhoc',label:'Ask a question'}] as const
const refreshDocument = () => resumeTab.value ? regenerateResume() : regenerateCoverLetter()
const saveDocument = () => resumeTab.value ? saveEditedResume() : saveEditedCoverLetter()
const editDocument = () => { if(resumeTab.value) { editableResumeMarkdown.value=props.assets.resume_markdown || '';isEditingResume.value=true } else { editableLetterMarkdown.value=props.assets.cover_letter_markdown || '';isEditingLetter.value=true } }
const cancelDocument = () => resumeTab.value ? cancelEditResume() : cancelEditLetter()
defineExpose({ unsaved })
</script>

<template>
  <section class="editor" aria-label="Application materials">
    <nav class="tabs doc-tabs" aria-label="Application materials"><button v-for="tab in materialTabs" :key="tab.value" :class="{active:activeTab===tab.value}" :aria-pressed="activeTab===tab.value" @click="activeTab=tab.value">{{ tab.label }}<span v-if="(tab.value==='cover_letter' && isEditingLetter) || (tab.value==='resume' && isEditingResume)" class="unsaved-dot" aria-label="Editing" /></button></nav>
    <div v-if="copyError" role="alert" class="feedback-error">{{ copyError }}</div>
    <template v-if="documentTab">
      <div class="doc-tools"><span>{{ editing ? 'Editing draft · Changes are not saved' : documentSaved ? 'Draft saved' : 'Tailored draft · Review before sending' }}</span><div class="actions"><template v-if="editing"><button :disabled="saving" @click="cancelDocument">Cancel</button><button class="primary" :disabled="saving" @click="saveDocument"><Save aria-hidden="true" />{{ saving ? 'Saving…' : 'Save draft' }}</button></template><template v-else><button :disabled="regenerating" @click="editDocument"><Edit3 aria-hidden="true" />Edit</button><button @click="copyToClipboard(documentText,'document')"><component :is="copiedField==='document' ? Check : Copy" aria-hidden="true" />{{ copiedField==='document' ? 'Copied' : 'Copy' }}</button><button :disabled="!documentText" :aria-label="`Download ${documentTitle} PDF`" @click="resumeTab ? downloadResumePdf() : downloadPdf()"><Download aria-hidden="true" /></button></template></div></div>
      <div v-if="documentError" role="alert" class="feedback-error">{{ documentError }}</div>
      <div class="paper-wrap" role="region" tabindex="0" :aria-label="`${documentTitle} document`"><details class="customize-panel"><summary>Customize {{ documentTitle.toLowerCase() }}</summary><div class="customize-fields"><label v-if="!resumeTab">Role focus<select v-model="selectedArchetype"><option v-for="role in roleArchetypes" :key="role.value" :value="role.value">{{ role.label }}</option></select></label><label>Instructions (optional)<textarea v-if="resumeTab" v-model="resumeDirectives" placeholder="What should the resume emphasize?" /><textarea v-else v-model="candidateDirectives" placeholder="What should the letter emphasize?" /></label><button class="secondary" :disabled="regenerating || saving || editing" @click="refreshDocument"><RefreshCw :class="{'animate-spin':regenerating}" aria-hidden="true" />{{ regenerating ? 'Generating draft…' : 'Generate a new draft' }}</button><small>Uses the candidate profile version saved with this application and the original job description.</small></div></details>
        <article class="paper" :class="{ 'resume-paper': resumeTab }"><template v-if="editing"><label class="sr-only" :for="`draft-${jobId}`">Edit {{ documentTitle.toLowerCase() }}</label><textarea v-if="resumeTab" :id="`draft-${jobId}`" v-model="editableResumeMarkdown" class="paper-editor" /><textarea v-else :id="`draft-${jobId}`" v-model="editableLetterMarkdown" class="paper-editor" /></template><template v-else><div v-if="!resumeTab" class="paper-heading"><h2>{{ assets.candidate_snapshot?.data?.name || 'Candidate' }}</h2><p>Application for {{ jobTitle || 'the role' }}<br>{{ companyName }}</p></div><MarkdownText v-if="documentText" :text="documentText" /><p v-else class="document-copy">No {{ documentTitle.toLowerCase() }} has been generated yet. Use Customize to prepare one.</p></template></article>
      </div>
    </template>
    <div v-else class="material-scroll" tabindex="0">
      <div v-if="activeTab==='answers'" class="answers-panel"><section v-for="(answer,index) in answers" :key="answer.label" class="answer"><div class="answer-head"><h3>{{ answer.label }}</h3><button @click="copyToClipboard(answerVariant(index).text,`answer-${index}`)"><component :is="copiedField===`answer-${index}` ? Check : Copy" aria-hidden="true" />{{ copiedField===`answer-${index}` ? 'Copied' : 'Copy' }}</button></div><div v-if="answer.variants.length>1" class="answer-lengths"><button v-for="(variant,i) in answer.variants" :key="i" :aria-pressed="(answerVersions[index] || 0)===i" @click="answerVersions[index]=i">{{ variant.max }} characters</button></div><p>{{ answerVariant(index).text || 'No answer has been generated.' }}</p><small :class="{'text-red-300':answerVariant(index).max && answerVariant(index).text?.length>answerVariant(index).max}">{{ answerVariant(index).text?.length || 0 }}{{ answerVariant(index).max ? ` / ${answerVariant(index).max}` : '' }} characters</small></section></div>
      <div v-else-if="activeTab==='contacts'" class="outreach-panel"><h2>Start a conversation</h2><p class="muted">Review the contact source before reaching out.</p><section v-if="hiringContacts?.primary_email" class="contact-block"><span class="tag" :class="{green:hiringContacts.is_direct_listing_email}">{{ hiringContacts.is_direct_listing_email ? 'Email found in listing' : 'Suggested inbox · Unverified' }}</span><strong>{{ hiringContacts.primary_email }}</strong><div class="actions"><button class="secondary" @click="copyToClipboard(hiringContacts.primary_email || '', 'email')"><Copy aria-hidden="true" />{{ copiedField==='email' ? 'Copied' : 'Copy email' }}</button><a :href="`mailto:${hiringContacts.primary_email}`" class="secondary button-link">Compose email</a></div><details v-if="hiringContacts.direct_emails?.length || hiringContacts.derived_inboxes?.length"><summary>Other discovered contacts</summary><p v-for="email in hiringContacts.direct_emails" :key="email">{{ email }} <small>Found in listing</small></p><p v-for="email in hiringContacts.derived_inboxes" :key="email">{{ email }} <small>Suggested · Unverified</small></p></details></section><p v-else class="contact-block muted">No hiring email is available. Use the original listing to find a contact.</p><a v-if="isCommunityOrFounder && /^https?:\/\//i.test(sourceUrl || '')" :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="text-link inline-link">Open original community post<ExternalLink aria-hidden="true" /></a><section class="customize-fields"><h3>Draft an introduction</h3><label>Recipient<select v-model="outreachPersona"><option value="technical_lead">Technical lead</option><option value="recruiter">Recruiter</option><option value="founder">Founder</option></select></label><label>Purpose<select v-model="outreachType"><option value="post_application">Follow up after applying</option><option value="direct_pitch">Introduce yourself</option></select></label><button class="secondary" :disabled="isGeneratingOutreach" @click="generateOutreach">{{ isGeneratingOutreach ? 'Writing…' : 'Generate outreach draft' }}</button><p v-if="outreachError" role="alert" class="feedback-error">{{ outreachError }}</p><div v-if="followUpPitchMessage"><label v-for="(subject,index) in outreachSubjects" :key="index" class="outreach-subject">Subject {{ index+1 }}<span>{{ subject }}</span><button @click="copyToClipboard(subject,`subject-${index}`)"><Copy />{{ copiedField===`subject-${index}` ? 'Copied' : 'Copy' }}</button></label><label>Message<textarea v-model="followUpPitchMessage" rows="10" /></label><button class="secondary" @click="copyToClipboard(followUpPitchMessage,'outreach')"><Copy />{{ copiedField==='outreach' ? 'Copied' : 'Copy message' }}</button></div></section></div>
      <div v-else class="outreach-panel"><h2>Answer a screening question</h2><p class="muted">Create a draft grounded in your saved profile and this role.</p><div class="customize-fields"><label>Question<textarea v-model="customQuestion" rows="4" placeholder="Paste the question from the application" /></label><label>Character limit<input v-model.number="customMaxChars" type="number" min="50" max="2000"></label><button class="primary" :disabled="isGenerating || customQuestion.trim().length<3 || customMaxChars<50 || customMaxChars>2000" @click="generateAdHocAnswer">{{ isGenerating ? 'Writing answer…' : 'Generate answer' }}</button><p v-if="adHocError" role="alert" class="feedback-error">{{ adHocError }}</p><section v-if="adHocAnswer" class="answer"><div class="answer-head"><h3>Suggested answer</h3><button @click="copyToClipboard(adHocAnswer,'adhoc')"><Copy />{{ copiedField==='adhoc' ? 'Copied' : 'Copy' }}</button></div><p>{{ adHocAnswer }}</p><small>{{ adHocAnswer.length }} / {{ customMaxChars }} characters · Review before sending</small></section></div></div>
    </div>
  </section>
</template>
