-- Idempotent upgrade for an existing PostgreSQL schema. Applied by `python -m app.db.database init`.
-- Missing tables are created first by SQLAlchemy; every statement here is safe to re-run.
-- Statements are split on semicolons: do not put a semicolon inside a string or comment.

ALTER TABLE sandbox_requests
    ADD COLUMN IF NOT EXISTS reference VARCHAR(20),
    ADD COLUMN IF NOT EXISTS business_unit_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS workload VARCHAR(100),
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS monthly_budget NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS requestor_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS requestor_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS manager_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS principal_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS subscription_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS expiry_date DATE,
    ADD COLUMN IF NOT EXISTS pending_expiry_date DATE,
    ADD COLUMN IF NOT EXISTS resource_id TEXT,
    ADD COLUMN IF NOT EXISTS imported BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS decision_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS decision_reason TEXT,
    ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS failed_operation VARCHAR(30),
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS operation_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS operation_in_progress VARCHAR(30),
    ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE sandbox_requests SET reference = 'LEGACY-' || substr(id::text, 1, 8) WHERE reference IS NULL;

ALTER TABLE sandbox_requests ALTER COLUMN reference SET NOT NULL;

ALTER TABLE sandbox_requests ALTER COLUMN duration_days DROP NOT NULL;

ALTER TABLE sandbox_requests DROP CONSTRAINT IF EXISTS chk_sandbox_request_status;

ALTER TABLE sandbox_requests ADD CONSTRAINT chk_sandbox_request_status CHECK (status IN
    ('pending', 'approved', 'rejected', 'provisioning', 'active', 'failed', 'decommissioning', 'decommissioned'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_sandbox_requests_reference ON sandbox_requests (reference);

CREATE INDEX IF NOT EXISTS idx_sandbox_requests_sandbox_name ON sandbox_requests (sandbox_name);

CREATE INDEX IF NOT EXISTS idx_sandbox_requests_created ON sandbox_requests (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sandbox_requests_updated ON sandbox_requests (updated_at);

CREATE INDEX IF NOT EXISTS idx_sandboxes_updated ON sandboxes (updated_at);

CREATE INDEX IF NOT EXISTS idx_extension_requests_updated ON extension_requests (updated_at);

CREATE INDEX IF NOT EXISTS idx_decommission_requests_updated ON decommission_requests (updated_at);

ALTER TABLE sandboxes ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE extension_requests
    ADD COLUMN IF NOT EXISTS reference VARCHAR(20),
    ADD COLUMN IF NOT EXISTS decision_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS decision_reason TEXT,
    ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE extension_requests SET reference = 'LEGACY-' || substr(id::text, 1, 8) WHERE reference IS NULL;

ALTER TABLE extension_requests ALTER COLUMN reference SET NOT NULL;

ALTER TABLE extension_requests DROP CONSTRAINT IF EXISTS chk_extension_status;

ALTER TABLE extension_requests ADD CONSTRAINT chk_extension_status CHECK (status IN
    ('pending', 'approved', 'rejected', 'completed', 'cancelled', 'failed'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_extension_requests_reference ON extension_requests (reference);

ALTER TABLE decommission_requests
    ADD COLUMN IF NOT EXISTS reference VARCHAR(20),
    ADD COLUMN IF NOT EXISTS requested_by_identity VARCHAR(255),
    ADD COLUMN IF NOT EXISTS source VARCHAR(30),
    ADD COLUMN IF NOT EXISTS expiry_date DATE,
    ADD COLUMN IF NOT EXISTS flagged_expiry DATE,
    ADD COLUMN IF NOT EXISTS cleanup_not_before DATE,
    ADD COLUMN IF NOT EXISTS decision_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS decision_reason TEXT,
    ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE decommission_requests SET reference = 'LEGACY-' || substr(id::text, 1, 8) WHERE reference IS NULL;

ALTER TABLE decommission_requests ALTER COLUMN reference SET NOT NULL;

ALTER TABLE decommission_requests ALTER COLUMN requested_by DROP NOT NULL;

ALTER TABLE decommission_requests DROP CONSTRAINT IF EXISTS chk_decommission_status;

ALTER TABLE decommission_requests ADD CONSTRAINT chk_decommission_status CHECK (status IN
    ('pending', 'approved', 'rejected', 'decommissioning', 'completed', 'failed', 'cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_decommission_requests_reference ON decommission_requests (reference);

ALTER TABLE terraform_jobs
    ADD COLUMN IF NOT EXISTS operation VARCHAR(30),
    ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE terraform_jobs DROP CONSTRAINT IF EXISTS chk_terraform_job_status;

ALTER TABLE terraform_jobs ADD CONSTRAINT chk_terraform_job_status CHECK (status IN
    ('pending', 'queued', 'running', 'success', 'completed', 'failed', 'cancelled', 'superseded'));

CREATE INDEX IF NOT EXISTS idx_terraform_jobs_queue ON terraform_jobs (created_at) WHERE status IN ('queued', 'running');

ALTER TABLE audit_logs ALTER COLUMN entity_id TYPE VARCHAR(100) USING entity_id::text;

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);

ALTER TABLE approvals DROP CONSTRAINT IF EXISTS chk_approval_decision;

ALTER TABLE approvals ADD CONSTRAINT chk_approval_decision CHECK (decision IN ('approved', 'rejected', 'pending'));

ALTER TABLE approvals DROP CONSTRAINT IF EXISTS chk_approval_request_reference;

ALTER TABLE approvals ADD CONSTRAINT chk_approval_request_reference CHECK
    (num_nonnulls(sandbox_request_id, extension_request_id, decommission_request_id) = 1);

CREATE INDEX IF NOT EXISTS idx_notifications_pending ON notifications (created_at) WHERE email_status = 'pending';

ALTER TABLE notifications
    ADD COLUMN IF NOT EXISTS owner_read_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS admin_read_at TIMESTAMPTZ;

INSERT INTO roles (id, name, description) VALUES
    (gen_random_uuid(), 'Admin', 'Manages sandbox requests and approvals'),
    (gen_random_uuid(), 'User', 'Can request and manage assigned sandboxes')
ON CONFLICT (name) DO NOTHING;
