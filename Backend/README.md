# Azure Sandbox Backend

For local setup, simulation, workflow checks and troubleshooting, see the
[local testing guide](../docs/local-testing.md).

Customer operating settings and rollout steps are covered in the
[customer-run deployment guide](../docs/customer-deployment.md). Pending customer
decisions and the meeting follow-up draft are in [customer-actions.md](../docs/customer-actions.md).

FastAPI serves the portal API. A separate worker provisions approved requests,
refreshes Azure billing data, creates lifecycle reminders, and delivers email.
The API never starts Terraform processes or imports local inventory on startup.

## Runtime Architecture

```text
Browser -> Next.js -> FastAPI -> Application database
                            -> durable operation records
Worker -> Application database -> Terraform / Azure Resource Manager / Cost Management / ACS
```

The application database stores request, approval, inventory, notification, operation, and audit
documents in `platform_records`. Existing repository contracts are retained;
`JSONStorageService` is a compatibility name, not a JSON-file storage engine.
Control-plane writes use a database mutex and nested transactions, so approvals,
audit records, and job creation commit or roll back together across API instances.
This favors correctness for a low-volume provisioning portal. Profile and normalize
the collection queries before adopting it for a high-volume service.

The worker holds a database session advisory lock while handling an operation.
Jobs have stable operation IDs and survive process restarts. Delivery is
at-least-once, not exactly-once: Terraform operations and deletion checks must remain
idempotent. Local SQLite uses a file lock instead. SQLite is rejected in production.
Use a direct database connection or session pooling, not transaction pooling,
because worker coordination uses session advisory locks.

## Terraform State Safety

Before generating variables, the worker preserves existing sandbox definitions
from the configured remote state, including those not yet present in the portal
inventory. It retains their ownership, budget start dates, and expiry values.
Incomplete state or conflicting ownership blocks the operation rather than
silently dropping an existing sandbox from the configuration.

Provisioning and extension jobs inspect a saved plan and refuse any deletion or
replacement before applying that exact plan. Keep `prevent_destroy` enabled.
State-only sandboxes are not automatically imported into the portal database;
reviewed inventory migration is still required to manage them through the portal.

## Local Development

Use Python 3.12. Configure the values in `.env.example` in your local `.env` or
environment. Existing `.env` files are not changed by this implementation.

From the Backend directory:

```powershell
python -m pip install -r requirements.txt
python -m app.db.database init
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Run the worker in a separate terminal, from the same directory and with the same
database/environment configuration:

```powershell
python -m app.worker
```

Starting the worker authorizes it to execute queued, approved operations. Do not
start it against a production database merely to test startup. `--once` executes
one operation and a maintenance pass; it is not a dry run. `TERRAFORM_ENABLED=false`
is a local simulation mode only and is refused in production.

```powershell
python -m pytest tests -q
python -m ruff check app tests
```

Tests isolate their own database and mock cloud operations. The default test backend
is temporary SQLite. To run against a dedicated integration-test database, set
`TEST_DATABASE_URL` to a database whose name begins with `sandbox_test`. Its platform
records will be cleared between tests. Never use application or production databases
for this setting. CI runs both database variants and builds the Linux containers.

## Legacy JSON Migration

1. Stop the old API and all provisioning processes. Back up `data`, the application database,
	and the Azure Storage Terraform state before changing anything.
2. Set `DATABASE_URL` to the new database and `ENTRA_TENANT_ID` to the tenant that
	owns the imported users. Initialize the schema once using the command above.
3. Review the JSON records, removing demo entries. Verify every `principal_id` and
	user/tenant binding. Imported ownership uses object IDs, never email matching.
4. Record each existing Azure budget's actual start timestamp as
	`budget_start_date` in its inventory record. If all existing budgets share one
	date, `LEGACY_BUDGET_START_DATE` can provide that explicit fallback. The worker
	refuses to invent or change legacy dates. New approvals persist their own date.
5. From Backend, run the explicit import:

```powershell
python -m app.db.database import-json --directory data
```

The import is transactional and refuses to overwrite a populated collection. It
does not contact Azure. Legacy inventory without corresponding request records is
converted into object-ID-bound imported requests as part of this explicit command,
not as an automatic startup action.

6. Confirm the configured remote-state resource group, account, container and key
	point to the existing state. The partial backend configuration does not copy or
	migrate state automatically. Never point a fresh inventory at unrelated state.
7. Review legacy role assignments. New requests can use the enabled built-in
	`Contributor` or `Owner` roles. Owner can grant access within the resource group;
	existing assignments are not silently changed.
8. Test a non-production request, extension, retry and deletion before reopening
	production. Preserve the old JSON backup until reconciliation is complete.

The sandbox detail page queries Azure resource inventory and month-to-date costs
using the backend's Azure identity. That identity needs resource read and Cost
Management read/query permissions at the sandbox resource-group scope. Cost data
can be delayed; resources without reported costs are not treated as zero.
Resource and cost results are cached for five minutes per backend process. Azure
rate limits are reported with a retry time rather than as permission failures.

## Azure App Service Deployment

Use two Linux App Service apps, one for the Node.js frontend and one for the API.
Run the worker as an always-running Azure Container App with at least one replica
and no ingress, or another supervised container host. Do not put the worker in a web
startup command. A manually triggered short-lived job is insufficient for the
continuous heartbeat and lifecycle scheduler without additional scheduling changes.

Build backend images from the repository root:

```powershell
docker build -f Backend/Dockerfile --target api -t sandbox-api .
docker build -f Backend/Dockerfile --target worker -t sandbox-worker .
```

The worker image contains Terraform, the reviewed modules and the provider lockfile;
it excludes local variables, state, credentials and provider caches. It uses the
Azure SDK for deletion, so Azure CLI is not a runtime dependency. Set the App Service
container target port to 8000 for the API and 3000 for the frontend.

For code-based API deployment, deploy Backend as the application root, enable
Oryx dependency installation, and use this custom ASGI startup command:

```sh
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Set these shared API/worker settings in Azure, not in deployed `.env` files:

| Setting | Production Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | TLS-enabled application database URL; use a Key Vault reference for credentials |
| `ENTRA_TENANT_ID` | Tenant GUID |
| `ENTRA_API_AUDIENCE` | Exact audience of the API's v2 access tokens |
| `ENTRA_REQUIRED_SCOPE` | `access_as_user`, or the actual exposed delegated scope name |
| `ENTRA_ALLOWED_CLIENT_IDS` | JSON array of trusted frontend application GUIDs |
| `ADMIN_ROLE` | `Sandboxadmin`, defined and assigned on the API registration |
| `ALLOWED_SANDBOX_ROLES` | `["Owner", "Contributor"]` |
| `CORS_ORIGINS` | JSON array of exact frontend HTTPS origins, with no trailing slash |
| `AZURE_SUBSCRIPTION_ID` | Dedicated sandbox subscription GUID |
| `BUDGET_CURRENCY` | Subscription billing currency; the current UI defaults to INR |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional Application Insights connection string |

Initialize the database as a release step before starting the API and worker.
Initialization is non-destructive `create_all`, not an automatic schema upgrade
engine. Version and review future schema changes; do not assume startup migrates
existing schemas. Use a separate initialization identity and a least-privilege
runtime database account where practical. Enable database backup/PITR.

Worker-specific settings:

| Setting | Production Value |
| --- | --- |
| `ARM_USE_MSI` | `true` for managed identity |
| `ARM_CLIENT_ID` | User-assigned managed identity client GUID, or unset for system identity |
| `TERRAFORM_ENVIRONMENT` | Environment tag, e.g. `prod` |
| `TERRAFORM_STATE_RESOURCE_GROUP` | Existing state-storage resource group |
| `TERRAFORM_STATE_STORAGE_ACCOUNT` | Existing state-storage account |
| `TERRAFORM_STATE_CONTAINER` | Existing state container |
| `TERRAFORM_STATE_KEY` | Isolated environment state key |
| `RUNTIME_DIRECTORY` | Writable worker scratch/log directory; use a persistent mount or external log export |
| `ACS_ENDPOINT` / `ACS_SENDER_ADDRESS` | Verified ACS Email endpoint and sender, if email is enabled |
| `ADMIN_NOTIFICATION_EMAILS` | JSON array of administrator email addresses |

For service-principal authentication instead of managed identity, set
`ARM_CLIENT_ID`, `ARM_TENANT_ID`, and `ARM_CLIENT_SECRET` through Key Vault references
and leave `ARM_USE_MSI=false`. Do not grant the web API the worker's provisioning
permissions. Restrict database and state-storage network access to the workloads.

The worker needs resource-management and deletion permissions in the dedicated
sandbox subscription, budget-management and Cost Management read permissions,
policy-definition/assignment permissions, and permission to create the custom role
and scoped role assignments. It also needs Storage Blob Data Contributor access to
the state container. Bootstrap subscription-level governance through a controlled
deployment identity where possible; avoid broad Owner grants. ACS identity-based
delivery requires its data-plane email sending permission. Verify effective access
in a non-production subscription rather than assuming a role name is sufficient.

## Entra And Frontend Configuration

Register the frontend as a SPA, register its exact HTTPS redirect URI, expose the
API delegated scope, grant consent, and assign the API's administrator role. Use
v2 API access tokens. The API validates the signature, issuer, audience, tenant,
expiry, delegated scope and allowed client. ID tokens are not API credentials.
Frontend navigation uses the API's verified `/auth/me` role response.

The frontend's `NEXT_PUBLIC_*` values are public build-time configuration. Build
separate images/artifacts for different public URLs or tenants. Do not expect a
runtime App Service setting to rewrite an already-built browser bundle. Build its
Dockerfile with all five build arguments from Frontend's `.env.example`. The image
uses Linux-built Next.js standalone output; do not deploy Windows-built symlinks.

## Lifecycle And Cost Semantics

- For admin-initiated decommission requests, the sandbox owner must explicitly
  agree before an administrator can approve cleanup. The initiating administrator
  may give final approval, but administrators cannot approve cleanup of their own sandbox.

- Expiry reminders and in-app notifications are durable and deduplicated. After
	expiry, a decommission request waits for an independent administrator's cleanup flag
	and the configured grace period. Resources continue charging until deletion. A rejected automatic request is not
  continually recreated for the same expiry date. Pending extensions must be
	decided before deletion can be approved. A pending extension also blocks queued
	cleanup execution, and an approved extension cancels prior cleanup flags.
- Extension approval stores a desired expiry. The applied expiry changes only
  after Terraform succeeds. Failed extension operations preserve the running
  sandbox and can be retried by an administrator.
- Costs are actual month-to-date Azure Cost Management query results, refreshed by
  the worker in bounded batches. Missing costs are `null`, not fabricated zeros.
  Azure billing data can be delayed. Mixed-currency totals are not compared against
  the budget. The UI does not fabricate earlier months.
- Azure budgets notify; they do not stop workloads or cap spend. The original Audit
	policy reports missing governance tags and is assigned only to sandbox resource groups.
  This does not constitute a complete region/SKU/network security policy baseline.
- In-app notifications work without ACS. Configure ACS before publishing events
  that need email. Delivery has five retry attempts and may duplicate across a
  crash after send but before acknowledgement. Inspect notification delivery state
  and logs for exhausted attempts; do not interpret an in-app notification as proof
  of delivered email.
- The status assistant uses retrieved sandbox data and rule-based responses; it
  is not an LLM integration and never invents spending data.

## Release Gates And Recovery

1. Require CI tests, lint, Terraform validation, Linux image builds and vulnerability scans to pass.
	These do not replace an Azure integration test.
2. In an isolated subscription/state/database, verify Entra login, denied access,
	independent approval, actual resource creation, tags, restricted RBAC, budgets,
	billing visibility, email and approved deletion. Check Azure propagation delays.
3. Restart the worker during an operation and verify reconciliation. Terraform's
	remote lock protects state, but a killed Terraform process can leave a stale
	lock. Confirm no runner remains before using a reviewed `terraform force-unlock`.
	Never automate force-unlock or state removal to resolve contention.
4. `/api/v1/health` is liveness; `/api/v1/ready` checks the database and, in production,
	a recent worker heartbeat. Use liveness for container restarts and readiness for
	release/traffic gates, so a worker outage does not cause web restart loops.
5. Enable HTTPS-only, supported TLS, Always On where applicable, resource limits,
	private networking, Application Insights and alerting. Monitor failed jobs,
	worker heartbeat, email failures and cost-refresh failures.
6. Keep staging subscriptions, state keys, databases and worker identities isolated.
	Do not warm a staging worker against production data. Drain/pause provisioning
	before access-policy/state changes. Only roll back between database-compatible
	application versions; returning to the pre-database implementation requires a
	planned migration and reconciliation. Never restore an old inventory over live Azure resources without
	reconciliation. Audit records are transactional but are not immutable/WORM logs;
	export them to your governed retention destination when that is required.
