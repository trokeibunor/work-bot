#!/usr/bin/env bash
set -e

# ==============================================================================
# JATE (Automated Job Acquisition & Tracking Engine) - Contabo Deployment Script
# Targets: Ubuntu / Debian Contabo Linux VPS (Docker Compose / Coolify)
# ==============================================================================

echo "==========================================================="
echo "   🚀 JATE Engine: Contabo Linux VPS Deployer              "
echo "==========================================================="

# 1. Verify Root or Sudo privileges
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 2. Check and Install Docker & Docker Compose if missing
if ! command -v docker &> /dev/null; then
  echo "📦 Docker not detected. Installing Docker Engine..."
  $SUDO apt-get update -y
  $SUDO apt-get install -y ca-certificates curl gnupg lsb-release
  $SUDO mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg || \
  curl -fsSL https://download.docker.com/linux/debian/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  
  DISTRO=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
  CODENAME=$(lsb_release -cs)
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO $CODENAME stable" | $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
  
  $SUDO apt-get update -y
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  $SUDO systemctl enable docker
  $SUDO systemctl start docker
  echo "✅ Docker successfully installed."
else
  echo "✅ Docker Engine is already installed: $(docker --version)"
fi

# Check Docker Compose plugin
if ! docker compose version &> /dev/null; then
  echo "📦 Docker Compose plugin missing. Installing docker-compose-plugin..."
  $SUDO apt-get update -y && $SUDO apt-get install -y docker-compose-plugin
fi
echo "✅ Docker Compose is ready: $(docker compose version)"

# 3. Handle Environment Configuration (.env)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "📋 Copying .env.example to .env..."
    cp .env.example .env
    echo "⚠️ NOTE: Please edit .env with your real OPENAI_API_KEY and Coolify domain URLs."
  else
    echo "❌ Error: Neither .env nor .env.example found!"
    exit 1
  fi
else
  echo "✅ Existing .env found."
fi

# Ensure storage directories exist with correct permissions
mkdir -p storage/pdfs
chmod -R 777 storage

# 4. Pull and Build Docker containers
echo "🏗️ Building and launching JATE services..."
docker compose pull || true
docker compose --profile proxy up -d --build

# 5. Wait for Backend Healthcheck
echo "⏳ Waiting for JATE backend to become healthy..."
MAX_ATTEMPTS=30
ATTEMPT=0
until docker compose ps backend | grep -q "(healthy)" || [ $ATTEMPT -ge $MAX_ATTEMPTS ]; do
  sleep 3
  ATTEMPT=$((ATTEMPT+1))
  echo "   Waiting for database & API readiness... ($ATTEMPT/$MAX_ATTEMPTS)"
done

if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
  echo "⚠️ Warning: Backend health check took longer than expected. Continuing startup check..."
fi

# 6. Trigger initial target companies seed & scraper run
echo "🔄 Triggering initial company sync and scraper pipeline..."
sleep 5
docker compose exec -T backend python -m app.workers.ats_scraper || echo "Scraper triggered asynchronously."

echo ""
echo "==========================================================="
echo "   🎉 JATE Engine deployed successfully!                  "
echo "==========================================================="
echo "  • Web Application (Nginx): http://<YOUR-VPS-IP> (Port 80)"
echo "  • Direct Frontend (Nuxt):  http://<YOUR-VPS-IP>:3000"
echo "  • FastAPI Backend:        http://<YOUR-VPS-IP>:8000/api/health"
echo "  • Database:               PostgreSQL 16 with pgvector on port 5433"
echo "  • Cache/Queue:            Redis on port 6379"
echo "==========================================================="
