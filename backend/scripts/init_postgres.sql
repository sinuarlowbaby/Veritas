-- ============================================================================
-- VERITAS — PostgreSQL Production Schema & pgvector Setup
-- ============================================================================

-- 1. Enable pgvector extension for high-performance vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Users table (authentication & multi-device session persistence)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 3. Verification Jobs table (persisted audits)
CREATE TABLE IF NOT EXISTS verification_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    claim_hash VARCHAR(64) NOT NULL,
    raw_claim TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'pending' NOT NULL,
    stage VARCHAR(32) DEFAULT 'queued',
    result_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    latency_ms DOUBLE PRECISION,
    token_count INTEGER DEFAULT 0,
    cached BOOLEAN DEFAULT FALSE,
    cache_type VARCHAR(32),
    similarity DOUBLE PRECISION,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_claim_hash ON verification_jobs(claim_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON verification_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON verification_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON verification_jobs(created_at DESC);

-- 4. Semantic Cache table (fast cosine similarity match for identical/rephrased claims)
CREATE TABLE IF NOT EXISTS semantic_cache (
    id SERIAL PRIMARY KEY,
    claim_text TEXT NOT NULL,
    claim_hash VARCHAR(64) NOT NULL,
    embedding vector(1536) NOT NULL,
    result_json TEXT NOT NULL,
    verdict VARCHAR(32),
    confidence DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_hash ON semantic_cache(claim_hash);
-- HNSW index for sub-5ms approximate nearest neighbors
CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding_hnsw 
    ON semantic_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 5. Curated Fact Checks table (RAG vector knowledge base of IFCN-certified verdicts)
CREATE TABLE IF NOT EXISTS curated_fact_checks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    source_url VARCHAR(1024) NOT NULL,
    source_name VARCHAR(128) NOT NULL,
    verdict VARCHAR(64) NOT NULL,
    publish_date VARCHAR(32) NOT NULL,
    chunk_index INTEGER DEFAULT 0 NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_curated_facts_source ON curated_fact_checks(source_name);
CREATE INDEX IF NOT EXISTS idx_curated_facts_verdict ON curated_fact_checks(verdict);
-- HNSW index for high-recall RAG retrieval
CREATE INDEX IF NOT EXISTS idx_curated_facts_embedding_hnsw 
    ON curated_fact_checks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 6. Feedback table (user accuracy ratings)
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) REFERENCES verification_jobs(job_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating VARCHAR(32) NOT NULL,
    verdict VARCHAR(64),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_job_id ON feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
