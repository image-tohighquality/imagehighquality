-- ============================================================
-- Image Quality Bot — Database Schema v1.5
-- Run this entire file in Supabase → SQL Editor → Run
-- ============================================================

-- Users table: one row per Telegram user
CREATE TABLE IF NOT EXISTS users (
    user_id      BIGINT PRIMARY KEY,
    username     TEXT,
    first_name   TEXT,
    joined_at    TIMESTAMPTZ DEFAULT NOW(),
    is_blocked   BOOLEAN DEFAULT FALSE
);

-- Requests table: one row per image analysis or patch request
CREATE TABLE IF NOT EXISTS requests (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    request_type     TEXT NOT NULL CHECK (request_type IN ('analyze', 'patch')),
    success          BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Index: rate limiting queries (user + time window)
CREATE INDEX IF NOT EXISTS idx_requests_user_time
    ON requests (user_id, created_at DESC);

-- Index: stats queries (time-based aggregations)
CREATE INDEX IF NOT EXISTS idx_requests_created
    ON requests (created_at DESC);

-- ============================================================
-- Verify setup
-- ============================================================
SELECT 'users table'    AS table_name, COUNT(*) AS rows FROM users
UNION ALL
SELECT 'requests table' AS table_name, COUNT(*) AS rows FROM requests;
