<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Copy, Check, Sparkles, Send, FileText, HelpCircle,
  MessageSquare, Mail, Edit3, Save, RefreshCw, Download,
  ExternalLink, UserCheck, ShieldCheck, CheckCircle2, AlertCircle,
  Briefcase, Rocket, Globe
} from 'lucide-vue-next'

interface AssetData {
  id: string
  cover_letter_markdown: string
  cover_letter_pdf_path?: string
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
const activeTab = ref<'answers' | 'cover_letter' | 'contacts' | 'adhoc'>('answers')

// Copy state tracking
const copiedField = ref<string | null>(null)

const copyToClipboard = async (text: string, fieldKey: string) => {
  try {
    await navigator.clipboard.writeText(text)
    copiedField.value = fieldKey
    setTimeout(() => {
      if (copiedField.value === fieldKey) {
        copiedField.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy to clipboard', err)
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
        role_archetype: selectedArchetype.value === 'auto' ? null : selectedArchetype.value,
        candidate_directives: candidateDirectives.value.trim() || null
      })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || `Failed to regenerate (${res.status})`)
    }

    const data = await res.json()
    props.assets.cover_letter_markdown = data.cover_letter_markdown
    editableLetterMarkdown.value = data.cover_letter_markdown
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
    props.assets.cover_letter_markdown = data.cover_letter_markdown
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

const buildPitchMessage = () => {
  if (isCommunityOrFounder.value) {
    return (
      `Hi ${props.companyName || 'Team'},\n\n` +
      `I came across your hiring post on ${getDirectCommunityPlatform()} for ${props.jobTitle || 'the engineering role'}. ` +
      `Given my background building resilient fintech systems at Sycamore (scaling customer platforms to 400,000+ users with an 84%+ fraud reduction) and concurrent Golang backend services at ALN Riders ($1M+ volume), ` +
      `I wanted to reach out directly to express my strong enthusiasm for what you're building.\n\n` +
      `I have prepared tailored materials and would love to connect directly regarding how my engineering background can accelerate your roadmap.\n\n` +
      `Portfolio: https://okeibunoremma.work\n` +
      `GitHub: https://github.com/okeibunoremmanuel\n` +
      `LinkedIn: https://linkedin.com/in/okeibunor-emmanuel\n\n` +
      `Best regards,\nEmmanuel Okeibunor\nokeibunoremma@gmail.com | +234 9015379412`
    )
  }
  return (
    `Hi ${props.companyName || 'Team'},\n\n` +
    `I recently submitted my application for the ${props.jobTitle || 'open role'}. ` +
    `With 5+ years of software engineering experience scaling high-concurrency Golang and Python/FastAPI services, ` +
    `as well as leading enterprise frontend systems at Sycamore (400k+ users), I am very eager to contribute to your engineering team.\n\n` +
    `I would love the opportunity to briefly introduce myself and share how my technical background aligns with your roadmap.\n\n` +
    `Portfolio: https://okeibunoremma.work\n` +
    `GitHub: https://github.com/okeibunoremmanuel\n` +
    `LinkedIn: https://linkedin.com/in/okeibunor-emmanuel\n\n` +
    `Best regards,\nEmmanuel Okeibunor\nokeibunoremma@gmail.com | +234 9015379412`
  )
}

const followUpPitchMessage = ref(buildPitchMessage())

// Recompute if props change
watch(() => [props.companyName, props.jobTitle, props.source, props.isFounderLed], () => {
  followUpPitchMessage.value = buildPitchMessage()
})
</script>

<template>
  <div class="glass-panel rounded-xl overflow-hidden border border-white/10 flex flex-col h-full">
    <!-- Header Tabs -->
    <div class="px-4 py-3 bg-dark-900/80 border-b border-white/10 flex items-center justify-between overflow-x-auto">
      <div class="flex items-center gap-1.5 p-1 rounded-lg bg-dark-850 border border-white/5">
        <button
          @click="activeTab = 'answers'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'answers' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <HelpCircle class="w-3.5 h-3.5" />
          <span>Screening Q&A</span>
        </button>

        <button
          @click="activeTab = 'cover_letter'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'cover_letter' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <FileText class="w-3.5 h-3.5" />
          <span>Cover Letter</span>
        </button>

        <!-- Hiring Contacts Tab with badge -->
        <button
          @click="activeTab = 'contacts'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'contacts' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <Mail class="w-3.5 h-3.5" />
          <span>Hiring Contacts</span>
          <span
            v-if="hiringContacts?.is_direct_listing_email"
            class="px-1.5 py-0.2 rounded-full text-[9px] font-mono font-bold bg-emerald-400 text-dark-950"
          >
            Direct
          </span>
          <span
            v-else-if="hiringContacts?.primary_email"
            class="px-1.5 py-0.2 rounded-full text-[9px] font-mono font-bold bg-white/20 text-white"
          >
            1+
          </span>
        </button>

        <button
          @click="activeTab = 'adhoc'"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all"
          :class="activeTab === 'adhoc' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'"
        >
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span>Ad-Hoc Copilot</span>
        </button>
      </div>

      <span class="text-[11px] text-slate-400 font-mono hidden md:inline ml-2">1-Click Fast Copy</span>
    </div>

    <!-- Content Body -->
    <div class="p-4 lg:p-6 overflow-y-auto space-y-6 flex-1">
      
      <!-- TAB 1: Screening Answers -->
      <div v-if="activeTab === 'answers'" class="space-y-4">
        
        <!-- Answer 1: Why Company (250 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Why this company? (Short &bull; 250 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_why_company_250?.length <= 250 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_why_company_250?.length || 0 }} / 250 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_why_company_250, 'why_250')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'why_250'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'why_250' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_why_company_250 }}
          </p>
        </div>

        <!-- Answer 2: Why Company (500 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Why this company? (Extended &bull; 500 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_why_company_500?.length <= 500 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_why_company_500?.length || 0 }} / 500 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_why_company_500, 'why_500')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'why_500'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'why_500' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_why_company_500 }}
          </p>
        </div>

        <!-- Answer 3: Technical Challenge (250 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Most complex technical challenge (250 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_technical_challenge_250?.length <= 250 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_technical_challenge_250?.length || 0 }} / 250 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_technical_challenge_250, 'tech_250')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'tech_250'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'tech_250' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_technical_challenge_250 }}
          </p>
        </div>

        <!-- Answer 4: Technical Challenge (500 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Most complex technical challenge (Extended &bull; 500 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_technical_challenge_500?.length <= 500 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_technical_challenge_500?.length || 0 }} / 500 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_technical_challenge_500, 'tech_500')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'tech_500'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'tech_500' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_technical_challenge_500 }}
          </p>
        </div>

        <!-- Answer 5: Python & Golang Proficiency (220 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Python & Golang Proficiency Statement (220 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_python_go_proficiency_220?.length <= 220 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_python_go_proficiency_220?.length || 0 }} / 220 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_python_go_proficiency_220, 'py_go_220')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'py_go_220'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'py_go_220' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_python_go_proficiency_220 }}
          </p>
        </div>

        <!-- Answer 6: Location & Relocation Readiness (220 chars) -->
        <div class="glass-card rounded-lg p-3.5 border border-white/5 hover:border-white/15 transition-all">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-200">Location & Relocation Statement (220 max)</span>
            <div class="flex items-center gap-2">
              <span
                class="text-[11px] font-mono px-2 py-0.5 rounded font-semibold"
                :class="assets.ans_location_relocation_220?.length <= 220 ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/15 text-red-400'"
              >
                {{ assets.ans_location_relocation_220?.length || 0 }} / 220 chars
              </span>
              <button
                @click="copyToClipboard(assets.ans_location_relocation_220, 'loc_220')"
                class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white transition-all active:scale-95"
              >
                <Check v-if="copiedField === 'loc_220'" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                <span>{{ copiedField === 'loc_220' ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
          <p class="text-xs text-slate-300 font-mono leading-relaxed bg-dark-950/60 p-2.5 rounded border border-white/5 select-all">
            {{ assets.ans_location_relocation_220 }}
          </p>
        </div>

      </div>

      <!-- TAB 2: Cover Letter Customization, Live Editor & PDF Generator -->
      <div v-else-if="activeTab === 'cover_letter'" class="space-y-4">
        
        <!-- Role Archetype Customization Bar -->
        <div class="glass-card rounded-xl p-4 border border-white/10 space-y-3 bg-dark-900/70">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <Briefcase class="w-4 h-4 text-brand-400" />
              <span class="text-xs font-bold text-white">Role Archetype Customization</span>
            </div>
            <span class="text-[11px] text-slate-400">Tailors projects & emphasis specifically to target role</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <!-- Archetype Selector -->
            <div>
              <label class="block text-[11px] font-semibold text-slate-300 mb-1">Target Role Archetype:</label>
              <select
                v-model="selectedArchetype"
                class="w-full bg-dark-950 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-brand-500 cursor-pointer"
              >
                <option v-for="arc in roleArchetypes" :key="arc.value" :value="arc.value" class="bg-dark-950 text-white">
                  {{ arc.label }}
                </option>
              </select>
            </div>

            <!-- Custom Directives -->
            <div>
              <label class="block text-[11px] font-semibold text-slate-300 mb-1">Candidate Directives / Extra Focus (Optional):</label>
              <input
                v-model="candidateDirectives"
                type="text"
                placeholder="e.g. Focus on Golang concurrency, ALN Riders $1M+ volume..."
                class="w-full bg-dark-950 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <!-- Action Buttons for Regeneration & PDF -->
          <div class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5">
            <button
              @click="regenerateCoverLetter"
              :disabled="isRegeneratingLetter"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-glow-indigo transition-all disabled:opacity-50"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isRegeneratingLetter }" />
              <span>{{ isRegeneratingLetter ? 'Regenerating & Recompiling PDF...' : 'Regenerate Cover Letter' }}</span>
            </button>

            <div class="flex items-center gap-2">
              <button
                v-if="!isEditingLetter"
                @click="isEditingLetter = true"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-dark-850 hover:bg-dark-800 text-slate-300 hover:text-white border border-white/10 text-xs font-semibold transition-colors"
              >
                <Edit3 class="w-3.5 h-3.5" />
                <span>Edit Text</span>
              </button>

              <button
                @click="downloadPdf"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-white text-xs font-semibold transition-colors shadow-glow-green"
              >
                <Download class="w-3.5 h-3.5" />
                <span>View Single-Page PDF</span>
              </button>
            </div>
          </div>

          <!-- Success / Error Alerts -->
          <div v-if="letterSavedSuccess" class="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 class="w-3.5 h-3.5" />
            <span>Cover letter & PDF recompiled successfully!</span>
          </div>

          <div v-if="letterError" class="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
            <AlertCircle class="w-3.5 h-3.5" />
            <span>{{ letterError }}</span>
          </div>
        </div>

        <!-- Cover Letter Content (Read or Edit Mode) -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-slate-200">
              {{ isEditingLetter ? 'Direct Markdown Editor' : 'Current Tailored Cover Letter' }}
            </span>

            <div class="flex items-center gap-2">
              <template v-if="isEditingLetter">
                <button
                  @click="cancelEditLetter"
                  class="px-2.5 py-1 rounded bg-dark-850 hover:bg-dark-800 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  @click="saveEditedCoverLetter"
                  :disabled="isSavingLetter"
                  class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs text-white font-semibold transition-all disabled:opacity-50 shadow-glow-green"
                >
                  <Save class="w-3.5 h-3.5" :class="{ 'animate-spin': isSavingLetter }" />
                  <span>{{ isSavingLetter ? 'Compiling PDF...' : 'Save & Recompile PDF' }}</span>
                </button>
              </template>

              <template v-else>
                <button
                  @click="copyToClipboard(assets.cover_letter_markdown, 'cover_letter')"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs text-white font-semibold shadow-glow-blue transition-all active:scale-95"
                >
                  <Check v-if="copiedField === 'cover_letter'" class="w-3.5 h-3.5 text-white" />
                  <Copy v-else class="w-3.5 h-3.5 text-white" />
                  <span>{{ copiedField === 'cover_letter' ? 'Copied!' : 'Copy Full Text' }}</span>
                </button>
              </template>
            </div>
          </div>

          <!-- Edit Textarea -->
          <div v-if="isEditingLetter">
            <textarea
              v-model="editableLetterMarkdown"
              rows="16"
              class="w-full p-4 rounded-lg bg-dark-950/90 border border-brand-500/40 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-brand-400"
              placeholder="Enter markdown cover letter..."
            ></textarea>
            <p class="text-[11px] text-slate-500 mt-1">
              Saving updates both the markdown content and regenerates the high-resolution single-page ReportLab PDF.
            </p>
          </div>

          <!-- Read-only Display -->
          <div
            v-else
            class="p-4 rounded-lg bg-dark-950/80 border border-white/5 text-xs text-slate-200 font-mono leading-relaxed whitespace-pre-wrap select-all max-h-[500px] overflow-y-auto"
          >
            {{ assets.cover_letter_markdown }}
          </div>
        </div>

      </div>

      <!-- TAB 3: Hiring Contacts & Follow-Up Inboxes -->
      <div v-else-if="activeTab === 'contacts'" class="space-y-4">
        
        <!-- Community / Founder Direct Channel Card -->
        <div v-if="isCommunityOrFounder" class="p-4 rounded-xl bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-dark-900 border border-amber-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-glow-amber">
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
              <Rocket class="w-5 h-5" />
            </div>
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-amber-300">Founder Direct Opportunity</span>
                <span class="px-1.5 py-0.2 rounded text-[10px] bg-amber-400/20 text-amber-200 border border-amber-400/30 font-mono font-semibold uppercase">
                  {{ getDirectCommunityPlatform() }}
                </span>
              </div>
              <div class="text-[11px] text-slate-300 mt-0.5">
                Direct founder or engineering lead hiring post. Direct outreach bypasses ATS filtering entirely.
              </div>
            </div>
          </div>

          <a
            v-if="sourceUrl"
            :href="sourceUrl"
            target="_blank"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-xs font-semibold whitespace-nowrap transition-all shadow-sm"
          >
            <span>Open Direct {{ getDirectCommunityPlatform() }} Post</span>
            <ExternalLink class="w-3.5 h-3.5" />
          </a>
        </div>

        <!-- Discovered Emails Card -->
        <div class="glass-card rounded-xl p-4 border border-white/10 space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Mail class="w-4 h-4 text-emerald-400" />
              <span class="text-xs font-bold text-white">Discovered Hiring & Recruiting Contacts</span>
            </div>
            <span
              v-if="hiringContacts?.is_direct_listing_email"
              class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono font-semibold"
            >
              Direct Email in Listing
            </span>
            <span
              v-else
              class="px-2 py-0.5 rounded text-[10px] bg-dark-850 text-slate-400 border border-white/10 font-mono"
            >
              Derived Talent Inboxes
            </span>
          </div>

          <!-- Primary Email Highlight -->
          <div v-if="hiringContacts?.primary_email" class="p-3.5 rounded-lg bg-dark-950 border border-white/10 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-400">Primary Contact:</span>
              <div class="flex items-center gap-2">
                <button
                  @click="copyToClipboard(hiringContacts.primary_email, 'primary_email')"
                  class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white"
                >
                  <Check v-if="copiedField === 'primary_email'" class="w-3.5 h-3.5 text-emerald-400" />
                  <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                  <span>{{ copiedField === 'primary_email' ? 'Copied' : 'Copy Email' }}</span>
                </button>

                <a
                  :href="hiringContacts.mailto_url || `mailto:${hiringContacts.primary_email}`"
                  target="_blank"
                  class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white shadow-glow-blue transition-all"
                >
                  <ExternalLink class="w-3.5 h-3.5" />
                  <span>Open in Mail Client</span>
                </a>
              </div>
            </div>

            <div class="text-sm font-mono font-bold text-emerald-400 select-all">
              {{ hiringContacts.primary_email }}
            </div>
          </div>

          <!-- All Derived & Discovered Inboxes -->
          <div class="space-y-2">
            <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Discovered Inboxes & Channels:
            </span>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div
                v-for="email in [...new Set([...(hiringContacts?.direct_emails || []), ...(hiringContacts?.derived_inboxes || [])])]"
                :key="email"
                class="flex items-center justify-between p-2 rounded-lg bg-dark-900 border border-white/5 hover:border-white/15 transition-all text-xs"
              >
                <div class="flex items-center gap-1.5 overflow-hidden">
                  <Mail class="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span class="font-mono text-slate-200 truncate select-all">{{ email }}</span>
                </div>
                <button
                  @click="copyToClipboard(email, `email_${email}`)"
                  class="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10 shrink-0"
                  title="Copy email"
                >
                  <Check v-if="copiedField === `email_${email}`" class="w-3.5 h-3.5 text-emerald-400" />
                  <Copy v-else class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Follow-Up Message / Outreach Pitch -->
        <div class="glass-card rounded-xl p-4 border border-white/10 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Send class="w-4 h-4 text-brand-400" />
              <span class="text-xs font-bold text-white">Pre-composed Follow-Up Outreach Pitch</span>
            </div>

            <button
              @click="copyToClipboard(followUpPitchMessage, 'pitch_msg')"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs text-white font-semibold shadow-glow-blue transition-all"
            >
              <Check v-if="copiedField === 'pitch_msg'" class="w-3.5 h-3.5 text-white" />
              <Copy v-else class="w-3.5 h-3.5 text-white" />
              <span>{{ copiedField === 'pitch_msg' ? 'Copied Pitch!' : 'Copy Outreach Message' }}</span>
            </button>
          </div>

          <textarea
            v-model="followUpPitchMessage"
            rows="8"
            class="w-full p-3 rounded-lg bg-dark-950/80 border border-white/5 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-brand-500"
          ></textarea>
        </div>

      </div>

      <!-- TAB 4: Ad-Hoc Copilot Box -->
      <div v-else-if="activeTab === 'adhoc'" class="space-y-4">
        <div class="glass-card rounded-xl p-4 border border-white/10 space-y-4">
          <div class="flex items-center gap-2 text-xs font-bold text-amber-300">
            <Sparkles class="w-4 h-4 text-amber-400" />
            <span>Ad-Hoc Application Question Solver</span>
          </div>
          <p class="text-xs text-slate-400">
            Encountered an unexpected screening question on the application portal? Paste it here to generate a tailored answer strictly fitted to Emmanuel's verified profile in &lt; 2 seconds.
          </p>

          <!-- Input -->
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1.5">Application Question:</label>
            <textarea
              v-model="customQuestion"
              rows="2"
              placeholder="e.g. Describe your experience scaling high-concurrency microservices or handling production incidents..."
              class="w-full p-2.5 bg-dark-900 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
            ></textarea>
          </div>

          <!-- Slider -->
          <div class="flex items-center justify-between gap-4 text-xs">
            <div class="flex items-center gap-2">
              <span class="text-slate-300">Max Character Limit:</span>
              <span class="font-mono font-bold text-white bg-dark-900 px-2 py-0.5 rounded border border-white/10">{{ customMaxChars }} chars</span>
            </div>
            <input
              type="range"
              min="50"
              max="1000"
              step="10"
              v-model.number="customMaxChars"
              class="w-44 accent-brand-500 cursor-pointer"
            />
          </div>

          <!-- Submit Button -->
          <button
            @click="generateAdHocAnswer"
            :disabled="!customQuestion.trim() || isGenerating"
            class="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-xs font-bold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-glow-blue"
          >
            <Send class="w-3.5 h-3.5" :class="{ 'animate-pulse': isGenerating }" />
            <span>{{ isGenerating ? 'Synthesizing with LLM (< 2s)...' : 'Generate Tailored Answer' }}</span>
          </button>

          <!-- Result Area -->
          <div v-if="adHocAnswer" class="mt-4 p-3 bg-dark-950 rounded-lg border border-brand-500/30 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="font-semibold text-slate-300">Generated Answer:</span>
              <div class="flex items-center gap-2">
                <span class="font-mono text-[11px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold">
                  {{ adHocAnswer.length }} / {{ customMaxChars }} chars
                </span>
                <button
                  @click="copyToClipboard(adHocAnswer, 'adhoc')"
                  class="flex items-center gap-1 px-2.5 py-1 rounded bg-white/10 hover:bg-white/15 text-xs text-white"
                >
                  <Check v-if="copiedField === 'adhoc'" class="w-3.5 h-3.5 text-emerald-400" />
                  <Copy v-else class="w-3.5 h-3.5 text-slate-300" />
                  <span>{{ copiedField === 'adhoc' ? 'Copied!' : 'Copy' }}</span>
                </button>
              </div>
            </div>
            <p class="text-xs text-slate-200 font-mono leading-relaxed bg-dark-900/90 p-2.5 rounded border border-white/5 select-all">
              {{ adHocAnswer }}
            </p>
          </div>

          <div v-if="adHocError" class="text-xs text-red-400">
            {{ adHocError }}
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
