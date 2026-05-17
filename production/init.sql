-- Initialize the custom extension tables for CSIR/GATE Open WebUI modifications

-- 1. Subscription Plans
CREATE TABLE IF NOT EXISTS ext_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL, -- e.g., 'CSIRCHEM_BASIC'
    price DECIMAL(10, 2) NOT NULL,
    exam VARCHAR(100) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    folder_name VARCHAR(255) NOT NULL,
    validity_days INTEGER NOT NULL,
    notes_model VARCHAR(255) NOT NULL, -- Maps to Open WebUI native model ID (e.g., 'gpt-4o')
    mcq_model VARCHAR(255) NOT NULL, -- Maps to Open WebUI native model ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. User Access & Subscriptions
CREATE TABLE IF NOT EXISTS ext_user_access (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- Links to Open WebUI core 'user' table
    plan_id INTEGER NOT NULL REFERENCES ext_plans(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'expired', 'cancelled'
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_active_plan UNIQUE (user_id, plan_id, status)
);

CREATE INDEX IF NOT EXISTS idx_user_access_status ON ext_user_access(user_id, status);

-- 3. Chat Tags (for Smart Router and History UI filtering)
CREATE TABLE IF NOT EXISTS ext_chat_tags (
    chat_id VARCHAR(255) PRIMARY KEY, -- Open WebUI's native chat ID
    user_id VARCHAR(255) NOT NULL,
    data_function VARCHAR(50) NOT NULL, -- e.g., 'ask_agent' or 'mcq_widget'
    exam VARCHAR(100) DEFAULT 'General',
    subject VARCHAR(255) DEFAULT 'General',
    topic VARCHAR(255) DEFAULT 'General',
    lesson VARCHAR(255) DEFAULT 'General',
    concept VARCHAR(255) DEFAULT 'General',
    level VARCHAR(50) DEFAULT '',     -- e.g., 'basic', 'intermediate', 'advanced' (MCQ widget)
    number VARCHAR(50) DEFAULT '',    -- e.g., '5' (number of MCQs); kept as text for flexibility
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Backfill columns for pre-existing deployments (idempotent; safe on fresh installs too)
ALTER TABLE ext_chat_tags ADD COLUMN IF NOT EXISTS level VARCHAR(50) DEFAULT '';
ALTER TABLE ext_chat_tags ADD COLUMN IF NOT EXISTS number VARCHAR(50) DEFAULT '';

-- Index for Smart Router lookup (fetching existing chat for a specific payload identity).
-- Includes level + number so e.g. MCQ basic/intermediate/advanced for the same concept
-- are recognised as distinct chats.
CREATE INDEX IF NOT EXISTS idx_chat_tags_router
    ON ext_chat_tags(user_id, data_function, concept, level, number);
-- Index for History UI filtering
CREATE INDEX IF NOT EXISTS idx_chat_tags_history
    ON ext_chat_tags(user_id, exam, subject, topic, lesson);

-- 4. Operational Audit Log
--
-- Scope: server-side audit / performance trace only. Token counts and cost
-- accounting were intentionally REMOVED — billing/usage is observed via the
-- Open WebUI admin panel and the vendor portals (Azure / OpenAI), not from
-- this overlay. Keep this table to a bare minimum so writes never become a
-- hot-path cost and the table is cheap to retain.
CREATE TABLE IF NOT EXISTS ext_audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,           -- 'anonymous' is allowed for unauthenticated paths
    endpoint_type VARCHAR(100) NOT NULL,     -- 'lookup', 'chat_tagged', 'history_fetched', 'prompt_template_fetched', ...
    model VARCHAR(255) NOT NULL DEFAULT '',  -- best-effort; '' when not derivable from request
    request_duration_ms INTEGER NOT NULL DEFAULT 0,
    -- Minimal correlation fields. Each is OPTIONAL; populate only what the
    -- caller already knows so the audit row stays a thin trace, not a ledger.
    request_id VARCHAR(64) DEFAULT NULL,     -- per-request id for cross-system correlation
    chat_id VARCHAR(255) DEFAULT NULL,       -- present for chat-scoped events (tag, lookup-hit)
    exam VARCHAR(100) DEFAULT NULL,
    subject VARCHAR(255) DEFAULT NULL,
    function VARCHAR(50) DEFAULT NULL,       -- data_function: 'ask_agent', 'mcq_widget', ...
    status VARCHAR(32) DEFAULT NULL,         -- 'hit' / 'miss' / 'ok' / 'error'
    meta JSONB DEFAULT NULL,                 -- small free-form correlation blob; NEVER prompt text or PII
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Idempotent drops for prior deployments that included token / cost / cache columns.
-- Safe on fresh installs (IF EXISTS no-ops). Run init.sql against an existing DB
-- to remove the now-deprecated billing columns.
ALTER TABLE ext_audit_logs DROP COLUMN IF EXISTS prompt_tokens;
ALTER TABLE ext_audit_logs DROP COLUMN IF EXISTS completion_tokens;
ALTER TABLE ext_audit_logs DROP COLUMN IF EXISTS total_cost;
ALTER TABLE ext_audit_logs DROP COLUMN IF EXISTS is_cache_hit;

-- Idempotent adds for prior deployments missing the new correlation columns.
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS chat_id VARCHAR(255);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS exam VARCHAR(100);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS subject VARCHAR(255);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS function VARCHAR(50);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS status VARCHAR(32);
ALTER TABLE ext_audit_logs ADD COLUMN IF NOT EXISTS meta JSONB;

CREATE INDEX IF NOT EXISTS idx_audit_user           ON ext_audit_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_endpoint_time  ON ext_audit_logs(endpoint_type, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_request_id     ON ext_audit_logs(request_id);

-- ══════════════════════════════════════════════════════════════════════════════
-- ENTITLEMENT SYSTEM (Phase 2 additions — idempotent on fresh and existing DBs)
-- ══════════════════════════════════════════════════════════════════════════════

-- 5. Evolve ext_plans to support the folder_key entitlement model.
--
--    plan_key   — stable slug used by entitlement lookups (e.g. 'trial', 'csir_chem_full').
--                 Replaces ad-hoc lookups by exam+subject+folder_name.
--    always_active — when true the backend auto-provisions 'unlocked' for every user
--                    on their first entitlement call. Used for the free Trial plan.
--    folder_keys   — JSONB array of folder_key strings this plan grants access to.
--                    Decoupled from physical paths; folder renames only require
--                    updating metadata.json, never this table.
ALTER TABLE ext_plans ADD COLUMN IF NOT EXISTS plan_key      VARCHAR(100);
ALTER TABLE ext_plans ADD COLUMN IF NOT EXISTS always_active BOOLEAN DEFAULT false;
ALTER TABLE ext_plans ADD COLUMN IF NOT EXISTS folder_keys   JSONB   DEFAULT '[]';

-- Backfill plan_key for any pre-existing rows (idempotent via WHERE guard).
UPDATE ext_plans
SET plan_key = lower(regexp_replace(name, '[^a-zA-Z0-9]+', '_', 'g'))
WHERE plan_key IS NULL OR plan_key = '';

-- Unique constraint on plan_key (deferred so backfill above runs first).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_ext_plans_plan_key'
    ) THEN
        ALTER TABLE ext_plans ADD CONSTRAINT uq_ext_plans_plan_key UNIQUE (plan_key);
    END IF;
END $$;

-- 6. User entitlements — keyed on (user_id, folder_key).
--
--    state values:
--      'unlocked' — active paid access (or always_active trial)
--      'expired'  — subscription lapsed; history still visible, new generation blocked
--      'locked'   — no purchase made
--
--    expires_at NULL means the entitlement never expires (used for always_active plans).
CREATE TABLE IF NOT EXISTS ext_user_entitlements (
    id           SERIAL PRIMARY KEY,
    user_id      VARCHAR(255) NOT NULL,
    exam_key     VARCHAR(100) NOT NULL DEFAULT '',
    subject_key  VARCHAR(255) NOT NULL DEFAULT '',
    folder_key   VARCHAR(100) NOT NULL,
    plan_key     VARCHAR(100) NOT NULL,
    state        VARCHAR(20)  NOT NULL DEFAULT 'locked'
                     CHECK (state IN ('unlocked', 'expired', 'locked')),
    activated_at TIMESTAMP WITH TIME ZONE,
    expires_at   TIMESTAMP WITH TIME ZONE,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_folder_entitlement UNIQUE (user_id, folder_key)
);

CREATE INDEX IF NOT EXISTS idx_entitlements_user_state
    ON ext_user_entitlements(user_id, state);
CREATE INDEX IF NOT EXISTS idx_entitlements_folder_state
    ON ext_user_entitlements(folder_key, state);

-- 7. Seed the Trial plan (always_active — auto-provisioned for every user).
--    folder_keys is intentionally empty here; populate it after creating
--    the Trial course folder and running scripts/generate_manifest.py.
--    Example: UPDATE ext_plans SET folder_keys = '["trial_pack"]' WHERE plan_key = 'trial';
INSERT INTO ext_plans (plan_key, name, price, exam, subject, folder_name,
                       validity_days, notes_model, mcq_model,
                       always_active, folder_keys)
VALUES ('trial', 'Trial Plan', 0.00, 'Trial', 'General', 'trial',
        36500, 'phi-4', 'phi-4',
        true, '[]')
ON CONFLICT (plan_key) DO NOTHING;
