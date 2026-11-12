import uuid

from sqlalchemy import (
    JSON, BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, MetaData, Numeric, String, Table, Text,
    Uuid, func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

Json = JSON().with_variant(JSONB(), "postgresql")
Timestamp = DateTime(timezone=True)


def _id() -> Column:
    return Column("id", Uuid, primary_key=True, default=uuid.uuid4)


def _created() -> Column:
    return Column("created_at", Timestamp, nullable=False, server_default=func.now())


def _updated() -> Column:
    return Column("updated_at", Timestamp, nullable=False, server_default=func.now())


# Document store kept only for small configuration collections (business units, subscription, heartbeat).
mutex = Table("platform_mutex", metadata, Column("id", Integer, primary_key=True))
records = Table(
    "platform_records", metadata,
    Column("collection", String(80), primary_key=True),
    Column("record_key", String(100), primary_key=True),
    Column("position", Integer, nullable=False),
    Column("document", JSON, nullable=False),
)

users = Table(
    "users", metadata, _id(),
    Column("entra_object_id", Uuid, nullable=False),
    Column("entra_tenant_id", Uuid, nullable=False),
    Column("email", String(255), nullable=False),
    Column("display_name", String(255)),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    _created(), _updated(),
    Index("uq_users_entra_identity", "entra_tenant_id", "entra_object_id", unique=True),
    Index("idx_users_email", "email"),
)

roles = Table(
    "roles", metadata, _id(),
    Column("name", String(50), nullable=False, unique=True),
    Column("description", String(255)),
    _created(),
)

user_roles = Table(
    "user_roles", metadata, _id(),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
    Column("assigned_at", Timestamp, nullable=False, server_default=func.now()),
    Index("uq_user_roles", "user_id", "role_id", unique=True),
    Index("idx_user_roles_role_id", "role_id"),
)

sandbox_requests = Table(
    "sandbox_requests", metadata, _id(),
    Column("reference", String(20), nullable=False),
    Column("requested_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("sandbox_name", String(150), nullable=False),
    Column("business_unit", String(100)),
    Column("business_unit_code", String(20)),
    Column("cost_center", String(100)),
    Column("workload", String(100)),
    Column("description", Text),
    Column("request_reason", Text),
    Column("location", String(100), nullable=False),
    Column("requested_role", String(50), nullable=False),
    Column("duration_days", Integer),
    Column("budget_amount", Numeric(12, 2)),
    Column("monthly_budget", Numeric(12, 2)),
    Column("owner_email", String(255)),
    Column("requestor_name", String(255)),
    Column("requestor_email", String(255)),
    Column("manager_email", String(255)),
    Column("principal_id", String(64)),
    Column("subscription_id", String(64)),
    Column("expiry_date", Date),
    Column("pending_expiry_date", Date),
    Column("resource_id", Text),
    Column("imported", Boolean, nullable=False, server_default="false"),
    Column("decision_by", String(255)),
    Column("decision_reason", Text),
    Column("decided_at", Timestamp),
    Column("failed_operation", String(30)),
    Column("last_error", Text),
    Column("operation_id", String(64)),
    Column("operation_in_progress", String(30)),
    Column("extra", Json, nullable=False, server_default="{}"),
    Column("status", String(30), nullable=False, server_default="pending"),
    _created(), _updated(),
    Index("uq_sandbox_requests_reference", "reference", unique=True),
    Index("idx_sandbox_requests_user", "requested_by"),
    Index("idx_sandbox_requests_status", "status"),
    Index("idx_sandbox_requests_sandbox_name", "sandbox_name"),
    Index("idx_sandbox_requests_created", "created_at"),
    Index("idx_sandbox_requests_updated", "updated_at"),
)

request_history = Table(
    "request_history", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("request_id", Uuid, ForeignKey("sandbox_requests.id", ondelete="CASCADE"), nullable=False),
    Column("status", String(50), nullable=False),
    Column("note", Text),
    Column("occurred_at", Timestamp, nullable=False, server_default=func.now()),
    Index("idx_request_history_request", "request_id", "id"),
)

sandboxes = Table(
    "sandboxes", metadata, _id(),
    Column("request_id", Uuid, ForeignKey("sandbox_requests.id"), nullable=False),
    Column("sandbox_id", String(150), nullable=False),
    Column("owner_user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("resource_group_name", String(150), nullable=False),
    Column("location", String(100), nullable=False),
    Column("assigned_role", String(50), nullable=False),
    Column("status", String(30), nullable=False, server_default="provisioning"),
    Column("budget_amount", Numeric(12, 2)),
    Column("provisioned_at", Timestamp),
    Column("expiry_date", Date),
    Column("decommissioned_at", Timestamp),
    Column("tags", Json, server_default="{}"),
    Column("extra", Json, nullable=False, server_default="{}"),
    _created(), _updated(),
    Index("uq_sandboxes_request", "request_id", unique=True),
    Index("uq_sandboxes_sandbox_id", "sandbox_id", unique=True),
    Index("idx_sandboxes_owner", "owner_user_id"),
    Index("idx_sandboxes_status", "status"),
    Index("idx_sandboxes_expiry", "expiry_date"),
)

extension_requests = Table(
    "extension_requests", metadata, _id(),
    Column("reference", String(20), nullable=False),
    Column("sandbox_id", Uuid, ForeignKey("sandboxes.id"), nullable=False),
    Column("requested_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("current_expiry_date", Date, nullable=False),
    Column("requested_expiry_date", Date, nullable=False),
    Column("extension_days", Integer, nullable=False),
    Column("reason", Text),
    Column("decision_by", String(255)),
    Column("decision_reason", Text),
    Column("extra", Json, nullable=False, server_default="{}"),
    Column("status", String(30), nullable=False, server_default="pending"),
    _created(), _updated(),
    Index("uq_extension_requests_reference", "reference", unique=True),
    Index("idx_extension_requests_sandbox", "sandbox_id"),
    Index("idx_extension_requests_status", "status"),
)

decommission_requests = Table(
    "decommission_requests", metadata, _id(),
    Column("reference", String(20), nullable=False),
    Column("sandbox_id", Uuid, ForeignKey("sandboxes.id"), nullable=False),
    Column("requested_by", Uuid, ForeignKey("users.id")),
    Column("requested_by_identity", String(255)),
    Column("source", String(30)),
    Column("reason", Text),
    Column("expiry_date", Date),
    Column("flagged_expiry", Date),
    Column("cleanup_not_before", Date),
    Column("decision_by", String(255)),
    Column("decision_reason", Text),
    Column("extra", Json, nullable=False, server_default="{}"),
    Column("status", String(30), nullable=False, server_default="pending"),
    _created(), _updated(),
    Index("uq_decommission_requests_reference", "reference", unique=True),
    Index("idx_decommission_sandbox", "sandbox_id"),
    Index("idx_decommission_status", "status"),
)

approvals = Table(
    "approvals", metadata, _id(),
    Column("sandbox_request_id", Uuid, ForeignKey("sandbox_requests.id")),
    Column("extension_request_id", Uuid, ForeignKey("extension_requests.id")),
    Column("decommission_request_id", Uuid, ForeignKey("decommission_requests.id")),
    Column("approver_user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("decision", String(20), nullable=False),
    Column("comments", Text),
    Column("approved_at", Timestamp),
    _created(),
    Index("idx_approvals_approver", "approver_user_id"),
    Index("idx_approvals_sandbox_request", "sandbox_request_id"),
    Index("idx_approvals_extension_request", "extension_request_id"),
    Index("idx_approvals_decommission_request", "decommission_request_id"),
)

terraform_jobs = Table(
    "terraform_jobs", metadata, _id(),
    Column("sandbox_id", Uuid, ForeignKey("sandboxes.id"), nullable=False),
    Column("triggered_by", Uuid, ForeignKey("users.id")),
    Column("job_type", String(30), nullable=False),
    Column("operation", String(30)),
    Column("status", String(30), nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("terraform_environment", String(50), server_default="dev"),
    Column("started_at", Timestamp),
    Column("completed_at", Timestamp),
    Column("exit_code", Integer),
    Column("summary", Text),
    Column("log_reference", Text),
    _created(), _updated(),
    Index("idx_terraform_jobs_sandbox", "sandbox_id"),
    Index("idx_terraform_jobs_status", "status"),
)

terraform_logs = Table(
    "terraform_logs", metadata, _id(),
    Column("job_id", Uuid, ForeignKey("terraform_jobs.id", ondelete="CASCADE"), nullable=False),
    Column("log_level", String(20), server_default="INFO"),
    Column("log_stream", String(20)),
    Column("message", Text),
    _created(),
    Index("idx_terraform_logs_job", "job_id"),
    Index("idx_terraform_logs_created", "created_at"),
)

audit_logs = Table(
    "audit_logs", metadata, _id(),
    Column("actor_user_id", Uuid, ForeignKey("users.id", ondelete="SET NULL")),
    Column("actor_identity", String(255)),
    Column("action", String(150), nullable=False),
    Column("entity_type", String(100)),
    Column("entity_id", String(100)),
    Column("details", Json, server_default="{}"),
    _created(),
    Index("idx_audit_logs_actor", "actor_user_id"),
    Index("idx_audit_logs_action", "action"),
    Index("idx_audit_logs_created", "created_at"),
    Index("idx_audit_logs_entity", "entity_type", "entity_id"),
)

sandbox_history = Table(
    "sandbox_history", metadata, _id(),
    Column("sandbox_id", Uuid, ForeignKey("sandboxes.id"), nullable=False),
    Column("changed_by", Uuid, ForeignKey("users.id", ondelete="SET NULL")),
    Column("previous_status", String(50)),
    Column("new_status", String(50), nullable=False),
    Column("change_reason", Text),
    Column("metadata", Json, server_default="{}"),
    Column("changed_at", Timestamp, nullable=False, server_default=func.now()),
    Index("idx_sandbox_history_sandbox", "sandbox_id"),
    Index("idx_sandbox_history_changed", "changed_at"),
)

notifications = Table(
    "notifications",  metadata,
    Column("id", String(64), primary_key=True),
    Column("request_id", Uuid, ForeignKey("sandbox_requests.id", ondelete="SET NULL")),
    Column("category", String(30), nullable=False),
    Column("title", Text, nullable=False),
    Column("audience", String(20), nullable=False),
    Column("recipient_text", Text),
    Column("recipients", Json, nullable=False, server_default="[]"),
    Column("cc_recipients", Json, nullable=False, server_default="[]"),
    Column("owner_object_id", String(64)),
    Column("owner_tenant_id", String(64)),
    Column("email_status", String(20), nullable=False, server_default="disabled"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("email_error", Text),
    _created(), _updated(),
    Index("idx_notifications_created", "created_at"),
    Index("idx_notifications_owner", "owner_object_id", "owner_tenant_id"),
    Index("idx_notifications_pending", "email_status", "attempts"),
)

reference_counters = Table(
    "reference_counters", metadata,
    Column("prefix", String(10), primary_key=True),
    Column("last_value", Integer, nullable=False),
)

ROLE_SEEDS = (("Admin", "Manages sandbox requests and approvals"), ("User", "Can request and manage assigned sandboxes"))
COUNTER_SEEDS = {"SBX": 1000, "EXT": 100, "DEC": 100}
