-- ==============================================================================
-- JATE: Automated Job Acquisition & Tracking Engine Database Schema
-- Compatible with PostgreSQL 16 + pgvector + uuid-ossp
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create Enums if they do not already exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM (
            'new',
            'queued_for_llm',
            'ready_to_apply',
            'applied',
            'rejected',
            'interview',
            'archived'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_source') THEN
        CREATE TYPE job_source AS ENUM (
            'greenhouse',
            'lever',
            'ashby',
            'workable',
            'reddit',
            'hackernews'
        );
    END IF;
END$$;

-- Table: target_companies
CREATE TABLE IF NOT EXISTS target_companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    ats_provider job_source NOT NULL,
    ats_slug VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    last_scraped_at TIMESTAMPTZ
);

-- Table: jobs
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(255) NOT NULL,
    source job_source NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    job_title TEXT NOT NULL,
    location_raw TEXT,
    is_remote_or_relocation_friendly BOOLEAN DEFAULT TRUE,
    description_raw TEXT NOT NULL,
    tech_stack_tags TEXT[] DEFAULT '{}',
    match_score INTEGER DEFAULT 0 CHECK (match_score >= 0 AND match_score <= 100),
    match_reasoning TEXT,
    is_founder_led BOOLEAN DEFAULT FALSE,
    status job_status DEFAULT 'new',
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    embedding VECTOR(1536)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_score ON jobs (status, match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs (source);
CREATE INDEX IF NOT EXISTS idx_jobs_founder_led ON jobs (is_founder_led);

-- Table: application_assets
CREATE TABLE IF NOT EXISTS application_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE UNIQUE,
    cover_letter_markdown TEXT NOT NULL,
    cover_letter_pdf_path TEXT,
    ans_why_company_250 VARCHAR(250) NOT NULL,
    ans_why_company_500 VARCHAR(500) NOT NULL,
    ans_technical_challenge_250 VARCHAR(250) NOT NULL,
    ans_technical_challenge_500 VARCHAR(500) NOT NULL,
    ans_python_go_proficiency_220 VARCHAR(220) NOT NULL,
    ans_location_relocation_220 VARCHAR(220) NOT NULL,
    custom_qa JSONB DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assets_job_id ON application_assets (job_id);

-- Seed Initial 30 Target Companies
INSERT INTO target_companies (name, ats_provider, ats_slug, is_active)
VALUES
    ('Stripe', 'greenhouse', 'stripe', true),
    ('GitLab', 'greenhouse', 'gitlab', true),
    ('Figma', 'greenhouse', 'figma', true),
    ('Vercel', 'greenhouse', 'vercel', true),
    ('Supabase', 'greenhouse', 'supabase', true),
    ('Datadog', 'greenhouse', 'datadog', true),
    ('Remote', 'greenhouse', 'remote', true),
    ('Deel', 'greenhouse', 'deel', true),
    ('Postman', 'greenhouse', 'postman', true),
    ('Monzo', 'greenhouse', 'monzo', true),
    ('Revolut', 'lever', 'revolut', true),
    ('Wise', 'lever', 'transferwise', true),
    ('Shopify', 'lever', 'shopify', true),
    ('Cloudflare', 'greenhouse', 'cloudflare', true),
    ('Linear', 'ashby', 'linear', true),
    ('Retool', 'ashby', 'retool', true),
    ('Ramp', 'ashby', 'ramp', true),
    ('Grafana Labs', 'greenhouse', 'grafana', true),
    ('HashiCorp', 'greenhouse', 'hashicorp', true),
    ('Canonical', 'greenhouse', 'canonical', true),
    ('Elastic', 'greenhouse', 'elastic', true),
    ('OpenAI', 'greenhouse', 'openai', true),
    ('Anthropic', 'lever', 'anthropic', true),
    ('Zapier', 'greenhouse', 'zapier', true),
    ('Docker', 'greenhouse', 'docker', true),
    ('GitHub', 'greenhouse', 'github', true),
    ('Brex', 'ashby', 'brex', true),
    ('dbt Labs', 'greenhouse', 'dbtlabs', true),
    ('Sourcegraph', 'greenhouse', 'sourcegraph', true),
    ('Fly.io', 'greenhouse', 'flyio', true)
ON CONFLICT (ats_slug) DO UPDATE
SET is_active = EXCLUDED.is_active;
