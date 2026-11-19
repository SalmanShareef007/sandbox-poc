-- Generated from Backend/app/db/tables.py

CREATE TABLE platform_mutex (
	id SERIAL NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE platform_records (
	collection VARCHAR(80) NOT NULL, 
	record_key VARCHAR(100) NOT NULL, 
	position INTEGER NOT NULL, 
	document JSON NOT NULL, 
	PRIMARY KEY (collection, record_key)
);


CREATE TABLE reference_counters (
	prefix VARCHAR(10) NOT NULL, 
	last_value INTEGER NOT NULL, 
	PRIMARY KEY (prefix)
);


CREATE TABLE roles (
	id UUID NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);


CREATE TABLE users (
	id UUID NOT NULL, 
	entra_object_id UUID NOT NULL, 
	entra_tenant_id UUID NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	display_name VARCHAR(255), 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX uq_users_entra_identity ON users (entra_tenant_id, entra_object_id);
CREATE INDEX idx_users_email ON users (email);

CREATE TABLE audit_logs (
	id UUID NOT NULL, 
	actor_user_id UUID, 
	actor_identity VARCHAR(255), 
	action VARCHAR(150) NOT NULL, 
	entity_type VARCHAR(100), 
	entity_id VARCHAR(100), 
	details JSONB DEFAULT '{}', 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_logs_action ON audit_logs (action);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_created ON audit_logs (created_at);
CREATE INDEX idx_audit_logs_actor ON audit_logs (actor_user_id);

CREATE TABLE sandbox_requests (
	id UUID NOT NULL, 
	reference VARCHAR(20) NOT NULL, 
	requested_by UUID NOT NULL, 
	sandbox_name VARCHAR(150) NOT NULL, 
	business_unit VARCHAR(100), 
	business_unit_code VARCHAR(20), 
	cost_center VARCHAR(100), 
	workload VARCHAR(100), 
	description TEXT, 
	request_reason TEXT, 
	location VARCHAR(100) NOT NULL, 
	requested_role VARCHAR(50) NOT NULL, 
	duration_days INTEGER, 
	budget_amount NUMERIC(12, 2), 
	monthly_budget NUMERIC(12, 2), 
	owner_email VARCHAR(255), 
	requestor_name VARCHAR(255), 
	requestor_email VARCHAR(255), 
	manager_email VARCHAR(255), 
	principal_id VARCHAR(64), 
	subscription_id VARCHAR(64), 
	expiry_date DATE, 
	pending_expiry_date DATE, 
	resource_id TEXT, 
	imported BOOLEAN DEFAULT 'false' NOT NULL, 
	decision_by VARCHAR(255), 
	decision_reason TEXT, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	failed_operation VARCHAR(30), 
	last_error TEXT, 
	operation_id VARCHAR(64), 
	operation_in_progress VARCHAR(30), 
	extra JSONB DEFAULT '{}' NOT NULL, 
	status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id)
);

CREATE INDEX idx_sandbox_requests_sandbox_name ON sandbox_requests (sandbox_name);
CREATE INDEX idx_sandbox_requests_created ON sandbox_requests (created_at);
CREATE INDEX idx_sandbox_requests_updated ON sandbox_requests (updated_at);
CREATE UNIQUE INDEX uq_sandbox_requests_reference ON sandbox_requests (reference);
CREATE INDEX idx_sandbox_requests_user ON sandbox_requests (requested_by);
CREATE INDEX idx_sandbox_requests_status ON sandbox_requests (status);

CREATE TABLE user_roles (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	role_id UUID NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_user_roles ON user_roles (user_id, role_id);
CREATE INDEX idx_user_roles_role_id ON user_roles (role_id);

CREATE TABLE notifications (
	id VARCHAR(64) NOT NULL, 
	request_id UUID, 
	category VARCHAR(30) NOT NULL, 
	title TEXT NOT NULL, 
	audience VARCHAR(20) NOT NULL, 
	recipient_text TEXT, 
	recipients JSONB DEFAULT '[]' NOT NULL, 
	cc_recipients JSONB DEFAULT '[]' NOT NULL, 
	owner_object_id VARCHAR(64), 
	owner_tenant_id VARCHAR(64), 
	email_status VARCHAR(20) DEFAULT 'disabled' NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	email_error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES sandbox_requests (id) ON DELETE SET NULL
);

CREATE INDEX idx_notifications_created ON notifications (created_at);
CREATE INDEX idx_notifications_owner ON notifications (owner_object_id, owner_tenant_id);
CREATE INDEX idx_notifications_pending ON notifications (email_status, attempts);

CREATE TABLE request_history (
	id BIGSERIAL NOT NULL, 
	request_id UUID NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	note TEXT, 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES sandbox_requests (id) ON DELETE CASCADE
);

CREATE INDEX idx_request_history_request ON request_history (request_id, id);

CREATE TABLE sandboxes (
	id UUID NOT NULL, 
	request_id UUID NOT NULL, 
	sandbox_id VARCHAR(150) NOT NULL, 
	owner_user_id UUID NOT NULL, 
	resource_group_name VARCHAR(150) NOT NULL, 
	location VARCHAR(100) NOT NULL, 
	assigned_role VARCHAR(50) NOT NULL, 
	status VARCHAR(30) DEFAULT 'provisioning' NOT NULL, 
	budget_amount NUMERIC(12, 2), 
	provisioned_at TIMESTAMP WITH TIME ZONE, 
	expiry_date DATE, 
	decommissioned_at TIMESTAMP WITH TIME ZONE, 
	tags JSONB DEFAULT '{}', 
	extra JSONB DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES sandbox_requests (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX uq_sandboxes_request ON sandboxes (request_id);
CREATE UNIQUE INDEX uq_sandboxes_sandbox_id ON sandboxes (sandbox_id);
CREATE INDEX idx_sandboxes_status ON sandboxes (status);
CREATE INDEX idx_sandboxes_owner ON sandboxes (owner_user_id);
CREATE INDEX idx_sandboxes_expiry ON sandboxes (expiry_date);

CREATE TABLE decommission_requests (
	id UUID NOT NULL, 
	reference VARCHAR(20) NOT NULL, 
	sandbox_id UUID NOT NULL, 
	requested_by UUID, 
	requested_by_identity VARCHAR(255), 
	source VARCHAR(30), 
	reason TEXT, 
	expiry_date DATE, 
	flagged_expiry DATE, 
	cleanup_not_before DATE, 
	decision_by VARCHAR(255), 
	decision_reason TEXT, 
	extra JSONB DEFAULT '{}' NOT NULL, 
	status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_id) REFERENCES sandboxes (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id)
);

CREATE INDEX idx_decommission_sandbox ON decommission_requests (sandbox_id);
CREATE UNIQUE INDEX uq_decommission_requests_reference ON decommission_requests (reference);
CREATE INDEX idx_decommission_status ON decommission_requests (status);

CREATE TABLE extension_requests (
	id UUID NOT NULL, 
	reference VARCHAR(20) NOT NULL, 
	sandbox_id UUID NOT NULL, 
	requested_by UUID NOT NULL, 
	current_expiry_date DATE NOT NULL, 
	requested_expiry_date DATE NOT NULL, 
	extension_days INTEGER NOT NULL, 
	reason TEXT, 
	decision_by VARCHAR(255), 
	decision_reason TEXT, 
	extra JSONB DEFAULT '{}' NOT NULL, 
	status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_id) REFERENCES sandboxes (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id)
);

CREATE INDEX idx_extension_requests_status ON extension_requests (status);
CREATE INDEX idx_extension_requests_sandbox ON extension_requests (sandbox_id);
CREATE UNIQUE INDEX uq_extension_requests_reference ON extension_requests (reference);

CREATE TABLE sandbox_history (
	id UUID NOT NULL, 
	sandbox_id UUID NOT NULL, 
	changed_by UUID, 
	previous_status VARCHAR(50), 
	new_status VARCHAR(50) NOT NULL, 
	change_reason TEXT, 
	metadata JSONB DEFAULT '{}', 
	changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_id) REFERENCES sandboxes (id), 
	FOREIGN KEY(changed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_sandbox_history_sandbox ON sandbox_history (sandbox_id);
CREATE INDEX idx_sandbox_history_changed ON sandbox_history (changed_at);

CREATE TABLE terraform_jobs (
	id UUID NOT NULL, 
	sandbox_id UUID NOT NULL, 
	triggered_by UUID, 
	job_type VARCHAR(30) NOT NULL, 
	operation VARCHAR(30), 
	status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	terraform_environment VARCHAR(50) DEFAULT 'dev', 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	exit_code INTEGER, 
	summary TEXT, 
	log_reference TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_id) REFERENCES sandboxes (id), 
	FOREIGN KEY(triggered_by) REFERENCES users (id)
);

CREATE INDEX idx_terraform_jobs_sandbox ON terraform_jobs (sandbox_id);
CREATE INDEX idx_terraform_jobs_status ON terraform_jobs (status);

CREATE TABLE approvals (
	id UUID NOT NULL, 
	sandbox_request_id UUID, 
	extension_request_id UUID, 
	decommission_request_id UUID, 
	approver_user_id UUID NOT NULL, 
	decision VARCHAR(20) NOT NULL, 
	comments TEXT, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_request_id) REFERENCES sandbox_requests (id), 
	FOREIGN KEY(extension_request_id) REFERENCES extension_requests (id), 
	FOREIGN KEY(decommission_request_id) REFERENCES decommission_requests (id), 
	FOREIGN KEY(approver_user_id) REFERENCES users (id)
);

CREATE INDEX idx_approvals_approver ON approvals (approver_user_id);
CREATE INDEX idx_approvals_sandbox_request ON approvals (sandbox_request_id);
CREATE INDEX idx_approvals_decommission_request ON approvals (decommission_request_id);
CREATE INDEX idx_approvals_extension_request ON approvals (extension_request_id);

CREATE TABLE terraform_logs (
	id UUID NOT NULL, 
	job_id UUID NOT NULL, 
	log_level VARCHAR(20) DEFAULT 'INFO', 
	log_stream VARCHAR(20), 
	message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES terraform_jobs (id) ON DELETE CASCADE
);

CREATE INDEX idx_terraform_logs_job ON terraform_logs (job_id);
CREATE INDEX idx_terraform_logs_created ON terraform_logs (created_at);

-- Upgrade / seed script (schema_upgrade.sql)

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

INSERT INTO roles (id, name, description) VALUES
    (gen_random_uuid(), 'Admin', 'Manages sandbox requests and approvals'),
    (gen_random_uuid(), 'User', 'Can request and manage assigned sandboxes')
ON CONFLICT (name) DO NOTHING;

