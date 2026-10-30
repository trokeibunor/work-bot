# Candidate profile workflow

The personal workspace now has a My Profile page at `/profile`. Existing context seeds the first database profile, replacing runtime reliance on Python constants. This is still a single personal workspace, not a multi-account recruitment service.

## Candidate flow

- Upload a text-based PDF or DOCX CV (10 MB, PDF limited to 50 pages). Originals are retained under the existing persistent storage volume. The worker extracts text and proposes a replacement profile. Scanned/unreadable PDFs receive an actionable request to paste text or use a text-based document; OCR is not implemented.
- Add project notes as text. The draft retains existing identity and employment, adds projects, and asks about missing responsibilities or outcomes. Duplicate project names are flagged for reconciliation rather than silently overwriting facts.
- Record up to three minutes of audio, or upload an audio file up to 20 MB. The worker creates an editable transcript and stops. Only after the candidate reviews the transcript does extraction start. Microphone permission, unsupported browsers, unavailable transcription, processing failures, and retry are handled explicitly. Clips and microphone tracks are cleaned up when leaving the page.
- Review the original source, warnings, and proposed fields. Save a draft or explicitly approve the facts. Every approval creates an immutable version, with optimistic concurrency checks against the active version. An outdated source must be analyzed again.
- Build the master CV from reviewed fields without inventing facts; edit its text if desired, and download PDF. Approved versions remain available to load as new drafts.

## Storage and application integration

PostgreSQL stores the active profile pointer, immutable versions, original source text, proposals, source statuses, and provenance. The existing startup migration lock serializes schema initialization and seeds the existing candidate context once. Existing application assets receive a historical snapshot; subsequent profile edits never rewrite their documents. New application assets capture the current approved context. Regeneration uses the snapshot for that application, including PDF headers, cover letters, answers, and outreach.

Personal claims were removed from generation fallbacks, role prompts, PDF filenames/headers, contact drafts, and the active application UI. Historical constants remain only for migration and compatibility with old documents. Scoring fallback compares the saved candidate's skills to a listing, and labels the result a keyword estimate.

CV parsing, project extraction, and transcription use Celery. Task reservations prevent duplicate deliveries from running the same source twice. Broker failures leave retryable source records; processing records older than ten minutes can also be retried. Source content is data, never system instructions. AI output is schema-validated and remains an unapproved draft.

## Configuration

Text extraction uses the workspace's existing configured text provider. If unavailable, raw text remains available and the candidate can complete profile fields manually. Voice uses `TRANSCRIPTION_API_KEY` or falls back to `OPENAI_API_KEY`; `TRANSCRIPTION_BASE_URL` and `TRANSCRIPTION_MODEL` are configurable, independently of the text provider. The UI exposes availability, never credentials. The local environment currently has text generation configured and no transcription key.

The transcription implementation follows the official [OpenAI Python transcription reference](https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create). Tests mock provider requests; no microphone recording or paid transcription is performed automatically.

## Verification

Production Nuxt/Docker builds; backend unit and PostgreSQL/ASGI tests covering extraction, identity isolation, claim-preserving fallback, PDF special characters, uploads, source review, voice transcript gating, approvals, version conflicts, task retries, and preservation of application snapshots. Database fixtures roll back; provider calls are mocked. Browser review covers desktop and 375px mobile, keyboard-accessible editing, CV preview, navigation and accessibility scans.

Run backend checks using the existing Docker test command with application and test directories mounted; set `RUN_DB_TESTS=1` for the local database integration tests.

## CV depth correction (2026-10-30)

The original migration seeded the profile from a condensed context, merging Numinix and Pertinence into an undated entry. The fuller source CV supplied separate dated roles. Restored the active personal profile and master CV as a new version, including Pertinence Group (Lead Frontend Developer, 03/2023–10/2024), Numinix (11/2024–03/2025), and detailed achievements from that source. Retained the newer approved ALN transaction figure rather than reverting to an older conflicting value.

Tailoring and CV extraction now explicitly preserve dated employment, leadership, scope, metrics, and substantive achievements, with no one-page limit. A deterministic output check verifies employer/title/period coverage, numerical evidence, and achievement bullet count; insufficient output falls back to the complete source CV. These checks detect structural loss, not semantic equivalence of every rephrased sentence. Regenerating an application with the known condensed legacy snapshot can use the same candidate’s repaired approved profile. Saved documents and downloaded files are not mass rewritten. Regression suite: 24 tests passed, including the migration correction and regeneration path.
