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

CREATE INDEX idx_user_access_status ON ext_user_access(user_id, status);

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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for Smart Router lookup (fetching existing chat for a specific concept)
CREATE INDEX idx_chat_tags_router ON ext_chat_tags(user_id, concept, data_function);
-- Index for History UI filtering
CREATE INDEX idx_chat_tags_history ON ext_chat_tags(user_id, exam, subject, topic, lesson);

-- 4. Audit & Token Logging
CREATE TABLE IF NOT EXISTS ext_audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    endpoint_type VARCHAR(100) NOT NULL, -- 'notes', 'mcq', 'free_form'
    model VARCHAR(255) NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10, 6) DEFAULT 0.0,
    request_duration_ms INTEGER DEFAULT 0,
    is_cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON ext_audit_logs(user_id, created_at);
