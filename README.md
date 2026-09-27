# 🚀 JATE — Automated Job Acquisition & Tracking Engine

**JATE** is an automated, high-velocity job application engine designed to ingest opportunities across ATS boards (Greenhouse, Lever, Ashby, Workable), Hacker News "Who is Hiring?", and Reddit. It leverages LLMs (Google Gemini / OpenAI) to analyze job descriptions against candidate context, auto-score match relevance, tailor cover letters and technical answers, and generate clean PDF resumes/cover letters.

---

## 🏛️ System Architecture

```text
[ Browser / Client ]
         │
         ▼ (Port 80 / 443)
┌────────────────────────────────────────────────────────┐
│                   Nginx Reverse Proxy                  │
│   • /api/*  ───► Forwarded to FastAPI Backend (8000)   │
│   • /*      ───► Forwarded to Nuxt 4 SSR (3000)        │
└────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────┐               ┌─────────────────────┐
│  Nuxt 4 Frontend │               │   FastAPI Backend   │
│  (Vue 3 / SSR)   │               │   (Python 3.12)     │
└──────────────────┘               └──────────┬──────────┘
                                              │
                   ┌──────────────────────────┼─────────────────────────┐
                   │                          │                         │
                   ▼                          ▼                         ▼
         ┌───────────────────┐      ┌───────────────────┐     ┌───────────────────┐
         │   PostgreSQL 16   │      │       Redis       │     │   Celery Worker   │
         │   (+ pgvector)    │      │ (Broker & Cache)  │     │   & Beat Sched.   │
         └───────────────────┘      └───────────────────┘     └───────────────────┘
```

---

## 📁 Repository Structure

```text
.
├── .env.example             # Template for all environment variables & secrets
├── .dockerignore            # Root docker ignore rules
├── .gitignore               # Comprehensive Git ignore rules (protects secrets & node_modules)
├── docker-compose.yml       # Production multi-container orchestration
├── docker-compose.dev.yml   # Dev override for local live-reload (bind mounts)
├── deploy-contabo.sh        # Turnkey 1-command deployment script for Ubuntu/Debian VPS
│
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI route controllers (jobs, assets, metrics)
│   │   ├── workers/         # Celery tasks (ATS scraper, HN scraper, Reddit, LLM tailor)
│   │   ├── utils/           # PDF generator, email finder
│   │   ├── candidate_context.py # Candidate profile ground truth
│   │   ├── config.py        # Pydantic BaseSettings config
│   │   ├── database.py      # SQLAlchemy asyncpg session setup
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   └── main.py          # FastAPI application entrypoint
│   ├── Dockerfile           # Backend container image
│   ├── entrypoint.sh        # DB readiness wait script
│   └── requirements.txt     # Python dependencies
│
├── frontend/
│   ├── app/                 # Nuxt 4 application pages & components
│   ├── assets/              # Tailwind CSS styles
│   ├── Dockerfile           # Multi-stage Nuxt SSR production container
│   ├── nuxt.config.ts       # Nuxt configuration
│   └── package.json         # Node dependencies
│
├── nginx/
│   └── nginx.conf           # Reverse proxy configuration (HTTP + WebSockets)
│
├── db/
│   └── init.sql             # PostgreSQL schema, pgvector extension & initial seed
│
└── storage/
    └── pdfs/                # Generated application PDFs volume
```

---

## 🔒 1. Initializing Git & Pushing Safely

To put this project on GitHub without exposing secrets or pushing bloated folders:

### Step 1: Initialize Git
```bash
git init
```

### Step 2: Verify Ignored Files
Make sure `.env` and `node_modules` are ignored:
```bash
git status
```
*Verify that `.env` and `frontend/node_modules/` do NOT appear in the list of untracked files.*

### Step 3: Commit Codebase
```bash
git add .
git commit -m "feat: initial production-ready JATE setup"
```

### Step 4: Link to GitHub & Push
```bash
# Rename branch to main
git branch -M main

# Add your GitHub repository remote
git remote add origin https://github.com/<your-username>/<your-repo-name>.git

# Push to private/public repository
git push -u origin main
```

---

## 💻 2. Local Development

### Option A: Running with Docker (Recommended)
```bash
# 1. Copy env file
cp .env.example .env

# 2. Start services with live-reload mounts
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
- Frontend: http://localhost:3000
- Backend API Docs: http://localhost:8000/docs

### Option B: Running Natively
```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

---

## 🌐 3. Hosting on a VPS (Little to No Complications)

There are two primary ways to host this on a VPS (Contabo, Hetzner, DigitalOcean, Linode, AWS EC2):

### Method 1: Bare VPS with Docker Compose & Nginx (Easiest)

This approach uses the built-in Nginx container as a single front door. Only port 80 (and 22 for SSH) needs to be open in your firewall.

1. **SSH into your VPS**:
   ```bash
   ssh root@<YOUR-VPS-IP>
   ```

2. **Clone your repository**:
   ```bash
   git clone https://github.com/<your-username>/<your-repo-name>.git
   cd <your-repo-name>
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   - Add your `GEMINI_API_KEY` (or `OPENAI_API_KEY`).
   - For single-domain/IP deployment, leave `NUXT_PUBLIC_API_BASE=` blank (uses relative `/api`).
   - Keep `COMPOSE_PROFILES=proxy` to enable Nginx.

4. **Run Turnkey Deployment Script**:
   ```bash
   chmod +x deploy-contabo.sh
   ./deploy-contabo.sh
   ```
   *This automatically installs Docker/Docker Compose if missing, builds images, runs migrations, and triggers initial company syncing.*

5. **Access Your Application**:
   - Open `http://<YOUR-VPS-IP>` in your browser!
   - Nginx routes all `/` requests to Nuxt and `/api/*` to FastAPI.

---

### Method 2: Deployment via Coolify (PaaS with Automated SSL)

If you use [Coolify](https://coolify.io) on your VPS:

1. In Coolify, create a **New Project** ➔ **Add Resource** ➔ **Public / Private Git Repository**.
2. Select your repository. Coolify will detect `docker-compose.yml`.
3. In **Environment Variables**:
   - Paste the contents of `.env.example`.
   - Add your `GEMINI_API_KEY` or `OPENAI_API_KEY`.
   - Set `NUXT_PUBLIC_API_BASE=https://api.yourdomain.com`.
   - Set `CORS_ORIGINS=["https://app.yourdomain.com"]`.
4. In **Domains Configuration**:
   - Point `https://app.yourdomain.com` to service `frontend` (Port 3000).
   - Point `https://api.yourdomain.com` to service `backend` (Port 8000).
   - Coolify's built-in Traefik automatically issues free Let's Encrypt SSL certificates.
5. Click **Deploy**.

---

## 🛠️ Maintenance & Operations

### View Real-time Logs
```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Celery scrapers / tailors
docker compose logs -f worker
```

### Manually Trigger Scrapers
```bash
# Greenhouse, Lever & Ashby company scraper
docker compose exec backend python -m app.workers.ats_scraper

# Hacker News "Who is Hiring?" scraper
docker compose exec backend python -m app.workers.hn_hiring_scraper

# Reddit founder scraper
docker compose exec backend python -m app.workers.reddit_listener
```

### Pull Updates & Redeploy
```bash
git pull origin main
docker compose --profile proxy up -d --build
```

### Database Backup
```bash
docker compose exec -T db pg_dump -U jate_admin jate_db > backup_$(date +%Y%m%d).sql
```
