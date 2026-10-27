-- ==============================================================================
-- RAIL / SIGNAL — Pipeline Execution History & Monitoring Schema
-- Table: pipeline_runs
-- Purpose: Authoritative execution history, stage monitoring, and audit log.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    pipeline_name VARCHAR(128) NOT NULL,
    run_type VARCHAR(32) NOT NULL DEFAULT 'VALIDATION',
    trigger_type VARCHAR(32) NOT NULL DEFAULT 'MANUAL_API',
    status VARCHAR(32) NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')),
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finish_time TIMESTAMPTZ,
    duration_seconds NUMERIC(10, 3),
    records_processed BIGINT NOT NULL DEFAULT 0,
    records_accepted BIGINT NOT NULL DEFAULT 0,
    records_quarantined BIGINT NOT NULL DEFAULT 0,
    current_stage VARCHAR(128),
    failed_stage VARCHAR(128),
    error_summary TEXT,
    stage_details JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance and lookup indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name ON pipeline_runs (pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_type ON pipeline_runs (run_type);
