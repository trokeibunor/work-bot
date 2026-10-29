<script setup lang="ts">
import { MapPin, Clock, ExternalLink, AlertTriangle } from 'lucide-vue-next'
import { jobTitle, jobLocation, jobSource, jobStatus, relativeDate, listingUrl } from '~/types/jobs'
import type { Job } from '~/types/jobs'
const props = defineProps<{ job: Job }>()
const reasoning = computed(() => props.job.match_reasoning?.trim() || '')
</script>
<template>
  <div class="company-line"><div class="company-logo" aria-hidden="true">{{ job.company_name?.[0] || '?' }}</div><div><strong>{{ job.company_name || 'Company unspecified' }}</strong><small>Via {{ jobSource(job.source) }}</small></div></div>
  <h2>{{ jobTitle(job) }}</h2>
  <div class="role-meta"><span><MapPin aria-hidden="true" />{{ jobLocation(job) }}</span><span><Clock aria-hidden="true" />{{ relativeDate(job.created_at) }}</span></div>
  <div class="tags"><span v-if="job.is_founder_led" class="tag blue">Founder-led</span><span class="tag" :class="{ green: job.status === 'ready_to_apply' || job.status === 'applied' }">{{ jobStatus(job.status) }}</span><span v-if="job.hiring_contacts?.is_direct_listing_email" class="tag">Hiring email available</span></div>
  <section class="detail-section"><div class="fit-heading"><h3>Why this could fit</h3><span class="fit-number">{{ job.status === 'queued_for_llm' || !job.match_score ? 'Not assessed' : `${job.match_score} / 100` }}</span></div><p class="fit-note">{{ reasoning ? reasoning.slice(0, 450) + (reasoning.length > 450 ? '…' : '') : 'No fit assessment yet. You can review the original listing while materials are prepared.' }}</p><details v-if="reasoning.length > 450" class="reasoning-details"><summary>Read full assessment</summary><p class="fit-note">{{ reasoning }}</p></details><small class="assessment-note">AI-assisted assessment. Review the requirements yourself.</small><div v-if="!job.location_raw?.trim()" class="caution"><AlertTriangle aria-hidden="true" /><span>The listing has no saved location. Confirm eligibility before applying.</span></div></section>
  <section v-if="job.tech_stack_tags?.length" class="detail-section"><h3>Technologies mentioned</h3><div class="tags"><span v-for="tag in job.tech_stack_tags" :key="tag" class="tag">{{ tag }}</span></div></section>
  <section class="detail-section"><h3>The opportunity</h3><p class="description source-description">{{ job.description_raw || 'No description was saved. Open the original listing to learn more.' }}</p><a v-if="listingUrl(job.source_url)" :href="listingUrl(job.source_url)" target="_blank" rel="noopener noreferrer" class="text-link inline-link">View original listing<ExternalLink aria-hidden="true" /></a></section>
</template>
