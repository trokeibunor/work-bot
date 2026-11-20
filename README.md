# 🚀 JATE — Automated Job Acquisition & Tracking Engine

**JATE** (Job Acquisition & Tracking Engine) is an automated, high-velocity job application platform. It ingests opportunities across ATS boards (Greenhouse, Lever, Ashby, Workable), Hacker News "Who is Hiring?", Reddit community threads, and manual uploads (PDF, CSV, XLSX, URLs, raw text). 

JATE leverages LLMs (Google Gemini, OpenAI, DeepSeek) against an immutable, user-approved candidate profile to auto-score match relevance, preserve professional resume depth, tailor cover letters and technical screening answers, generate cold outreach emails, and compile on-demand PDF assets.

---

## 🏛️ System Architecture

```text
                                  [ Browser / Client ]
                                            │
                                            ▼ (Port 80 / 443)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  Nginx Reverse Proxy                                   │
│   • /api/*   ─────────────────────► Forwarded to FastAPI Backend (8000)                │
│   • /*       ─────────────────────► Forwarded to Nuxt 4 SSR (3000)                     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
       ┌───────────────────────────┐                 ┌───────────────────────────┐
       │      Nuxt 4 Frontend      │                 │      FastAPI Backend      │
       │   (Vue 3 / SSR / Lucide)  │                 │    (Python 3.12 / ASGI)   │
       │  • / (Opportunities)      │                 │  • /api/jobs (Ingest/CRUD)│
       │  • /execute/:id (Tailor)  │                 │  • /api/candidate (Profile)│
       │  • /applications (Archive)│                 │  • /api/assets (PDFs/Gen) │
       │  • /automation (Scrapers) │                 │  • /api/metrics (Stats)   │
       │  • /profile (CV & Voice)  │                 └─────────────┬─────────────┘
       └───────────────────────────┘                               │
                                       ┌───────────────────────────┼───────────────────────────┐
                                       ▼                           ▼                           ▼
                            ┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
                            │    PostgreSQL 16    │     │       Redis 7       │     │    Celery Worker    │
                            │    (+ pgvector)     │     │  (Broker & Cache)   │     │    & Beat Sched.    │
                            │ • Jobs & Generated  │     │ • Queue dispatch    │     │ • ATS / HN / Reddit │
                            │   Org Type Column   │     │ • Result cache      │     │ • LLM Tailoring     │
                            │ • Candidate Profile │     │ • Locks & Sync      │     │ • CV / Audio Worker │
                            │   & Version Store   │     └─────────────────────┘     └─────────────────────┘
                            │ • ApplicationAssets │
                            │   (Locked Snapshot) │
                            └─────────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │   Storage Volume    │
                            │ (/app/storage/pdfs) │
                            │ • {job_id}/ (PDFs)  │
                            │ • candidate-cvs/    │
                            │ • candidate-sources/│
                            └─────────────────────┘
```

---

## ⚡ Core Engine & Data Pipelines

### 1. Ingestion Pipelines (Automated & Manual)
- **Automated ATS Scrapers**: Scrapes Greenhouse (`boards-api.greenhouse.io`), Lever (`api.lever.co`), and Ashby (`jobs.ashbyhq.com`) via Celery tasks every 6 hours.
- **Community Scrapers**:
  - **Hacker News**: Polls monthly "Ask HN: Who is hiring?" thread submissions every hour.
  - **Reddit Listener**: Scrapes target subreddits (`r/startups`, `r/forhire`, `r/Jobbit`, `r/remotejobs`, `r/golang`, `r/vuejs`, etc.) every 20 minutes with founder/early-hire keyword detection.
- **Manual Opportunity Ingestion**:
  - **Files**: Multi-format parsing of PDF job postings, CSV job lists, and XLSX spreadsheets.
  - **URLs**: Real-time HTTP scraping and structured text extraction from direct job links.
  - **Text**: Raw copy-pasted job listings parsed directly into the pipeline.
- **Classification & Pre-filtering**:
  - Stored PostgreSQL generated column derives `organization_type` (`nonprofit` vs `unknown`) using regex matching for charities, NGOs, and non-profit terms.
  - Keyword pre-filtering rejects irrelevant roles (e.g. US Clearance only, hardware) and tags technology stacks automatically.

### 2. Candidate Profile & Snapshot Isolation (`/profile`)
- **Single Personal Workspace**: Replaces hardcoded runtime constants with a database-backed candidate profile.
- **Multi-Modal Source Ingestion**:
  - Text-based PDF/DOCX CV upload (up to 10 MB, 50 pages).
  - Project notes as structured text.
  - Voice notes: Audio recording (up to 3 minutes) or audio file upload (up to 20 MB, MP3/WAV/M4A/WebM/OGG) transcribed via OpenAI/compatible audio transcriptions API (`TRANSCRIPTION_API_KEY`).
- **Human-in-the-Loop Approval**: Extracted facts are returned as proposals. The candidate reviews, edits, and explicitly approves facts.
- **Immutable Versioning**: Every approval creates an immutable `CandidateVersion`.
- **Application Snapshot Isolation**: Each tailored job application freezes a `candidate_snapshot` in `ApplicationAsset`. Profile edits never rewrite prior historical application documents.
- **Resume Depth Preservation (`resume_quality.py`)**: Deterministic checks verify that tailored CVs preserve every employer, title, full employment period, numerical metrics, and achievement bullets without artificial 1-page compression.

### 3. AI Application Tailoring (`/execute/:id`)
- **Multi-LLM Provider Support**: Compatible with Google Gemini (`gemini-flash-latest`), OpenAI (`gpt-4o-mini`), and DeepSeek (`deepseek-chat`).
- **Relevance Scoring**: 0–100 match score with detailed fit reasoning and founder-led indicators.
- **Generated Materials**:
  - Tailored Cover Letter (Markdown).
  - Tailored ATS Resume (Markdown).
  - Screening Questions: Why Company (250 & 500 chars), Technical Challenge (250 & 500 chars), Language/Stack Proficiency (220 chars), Relocation / Remote status (220 chars), custom QA questions.
  - Cold Outreach Email: Formats direct messages for hiring managers, founders, or recruiters.
- **On-Demand PDF Compilation**: Generated via ReportLab into isolated per-job storage directories (`storage/pdfs/{job_id}/...`) to prevent filename collisions across different roles at the same company.

---

## 📁 Repository Structure

```text
.
├── .env.example                  # Template for all environment variables & API keys
├── .dockerignore                 # Docker ignore rules
├── .gitignore                    # Git ignore rules (secrets, storage, node_modules)
├── docker-compose.yml            # Multi-container production orchestration (with DNS fallbacks)
├── docker-compose.dev.yml        # Development override with live-reload volume mounts
├── deploy-contabo.sh             # 1-command deployment script for Debian/Ubuntu VPS
├── db/
│   └── init.sql                  # PostgreSQL schema, pgvector extension & initial seed
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── jobs.py           # Ingestion, filtering, bulk actions, tailoring & Q&A
│   │   │   ├── candidate.py      # Profile management, CV/voice uploads, version approval
│   │   │   ├── assets.py         # On-demand PDF generation & file downloads
│   │   │   └── metrics.py        # Daily velocity metrics & manual scraper triggers
│   │   ├── services/
│   │   │   ├── candidate_profile.py # Profile context, snapshotting & resume markdown renderer
│   │   │   └── resume_quality.py    # Resume depth verification & metrics preservation
│   │   ├── workers/
│   │   │   ├── celery_app.py     # Celery instance, Beat schedules & transient cache rules
│   │   │   ├── ats_scraper.py    # Greenhouse, Lever & Ashby async scrapers
│   │   │   ├── hn_hiring_scraper.py # Hacker News "Who is Hiring?" monthly thread scraper
│   │   │   ├── reddit_listener.py   # Reddit hiring listener with founder detection
│   │   │   ├── candidate_profile.py # CV text extraction & audio transcription worker
│   │   │   └── llm_tailor.py     # Multi-provider LLM prompt builder & screening answers
│   │   ├── utils/
│   │   │   ├── pdf_generator.py  # ReportLab PDF compiler with directory isolation
│   │   │   ├── job_parser.py     # PDF, CSV, XLSX, URL, and raw text job ingest pipeline
│   │   │   └── email_finder.py   # Regex hiring manager contact & email extractor
│   │   ├── candidate_context.py  # Historical ground truth & migration seed
│   │   ├── candidate_schemas.py  # Pydantic models for candidate facts & proposals
│   │   ├── config.py             # Multi-provider settings (Gemini / OpenAI / DeepSeek)
│   │   ├── database.py           # SQLAlchemy asyncpg session engine
│   │   ├── models.py             # SQLAlchemy models & stored generated column
│   │   ├── schemas.py            # Pydantic schemas for API requests & responses
│   │   └── main.py               # FastAPI entrypoint, lifespan migration & CORS
│   ├── Dockerfile                # Multi-stage Python 3.12 image
│   ├── entrypoint.sh             # Database readiness wait script
│   └── requirements.txt          # Python dependencies
│
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── CandidateProfileEditor.vue # Fact editor, project review & CV viewer
│   │   │   ├── JobIngestModal.vue         # File, URL, and text job ingestion modal
│   │   │   ├── JobQueueTable.vue          # Opportunities table, filters & bulk bar
│   │   │   ├── JobPreview.vue             # Quick-inspect drawer for listing details
│   │   │   ├── AssetCopier.vue            # One-click copy for tailored screening answers
│   │   │   ├── ProfileLines.vue           # Dynamic multi-item editor for profile facts
│   │   │   ├── VelocityBar.vue            # Goal progress & daily application counter
│   │   │   └── MarkdownText.vue           # Markdown rendering component
│   │   ├── pages/
│   │   │   ├── index.vue                  # Opportunities dashboard (`/`)
│   │   │   ├── execute/[id].vue           # Application tailor, editor & executor (`/execute/:id`)
│   │   │   ├── applications.vue           # Submitted application tracker (`/applications`)
│   │   │   ├── automation.vue             # Scraper control & trigger panel (`/automation`)
│   │   │   └── profile.vue                # Candidate profile, CV & voice ingestion (`/profile`)
│   │   ├── composables/
│   │   │   ├── useApi.ts                  # API client fetch wrapper
│   │   │   └── useWorkspace.ts            # Global metrics, counts & state sync
│   │   ├── types/
│   │   │   ├── candidate.ts               # Candidate profile TypeScript interfaces
│   │   │   └── jobs.ts                    # Job, asset, and status types
│   │   ├── assets/css/main.css            # Dark-themed high-density CSS design system
│   │   └── app.vue                        # Layout shell with navigation & progress bar
│   ├── Dockerfile                         # Multi-stage Nuxt SSR container
│   ├── nuxt.config.ts                     # Nuxt 4 configuration
│   └── package.json                       # Node dependencies
│
├── docs/                                  # Architectural reviews & design specifications
├── nginx/
│   └── nginx.conf                         # Reverse proxy configuration
└── storage/
    └── pdfs/                              # Persistent application PDFs and uploaded sources
```

---

## 💻 Local Development

### Option A: Docker Compose (Recommended)
```bash
# 1. Clone environment variables
cp .env.example .env

# 2. Build and start services (with live reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
- **Web App**: `http://localhost:3000`
- **FastAPI Docs**: `http://localhost:8000/docs`

### Option B: Native Host Development
```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery Worker
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

---

## 🌐 Production VPS Deployment

### 1-Command Deployment (Ubuntu / Debian VPS)
```bash
# 1. SSH into VPS
ssh root@<YOUR-VPS-IP>

# 2. Clone repository
git clone https://github.com/<your-username>/work-bot.git
cd work-bot

# 3. Configure .env
cp .env.example .env
nano .env

# 4. Run turnkey deployment script
chmod +x deploy-contabo.sh
./deploy-contabo.sh
```

### Manual Docker Compose Deployment
```bash
docker compose --profile proxy up -d --build
```

---

## 🔧 Operational Runbook & Troubleshooting

### Viewing Service Logs
```bash
# All logs
docker compose logs -f

# Worker logs (scraping, extraction, tailoring)
docker compose logs -f worker

# Beat scheduler logs
docker compose logs -f beat

# API Backend logs
docker compose logs -f backend
```

### Diagnosing `[Errno -2] Name or service not known` (Worker DNS Failure)
If the worker outputs `[Errno -2] Name or service not known` during scraping:
1. **Cause**: The container cannot resolve external domain names (Greenhouse, Lever, Ashby, Reddit). This occurs when the host's DNS forwarder stalls (e.g. Docker Desktop after laptop sleep or Wi-Fi switch), or on a VPS when firewall/systemd-resolved blocks container DNS queries.
2. **Resolution**:
   - `docker-compose.yml` includes public fallback DNS (`8.8.8.8`, `1.1.1.1`) on `backend`, `worker`, and `beat`.
   - Recreate the containers:
     ```bash
     docker compose up -d --force-recreate worker beat
     ```
   - On a Linux VPS with UFW, ensure Docker traffic forwarding is allowed:
     ```bash
     # In /etc/default/ufw, set DEFAULT_FORWARD_POLICY="ACCEPT"
     sudo ufw reload
     ```

### Manually Triggering Tasks
```bash
# ATS company scraper (Greenhouse, Lever, Ashby)
docker compose exec backend python -m app.workers.ats_scraper

# Hacker News "Who is Hiring?" scraper
docker compose exec backend python -m app.workers.hn_hiring_scraper

# Reddit hiring listener
docker compose exec backend python -m app.workers.reddit_listener
```

### Database Backups & Schema Migrations
```bash
# Create snapshot backup
docker compose exec -T db pg_dump -U jate_admin jate_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore snapshot
docker compose exec -T db psql -U jate_admin -d jate_db < backup_20261102_120000.sql
```
