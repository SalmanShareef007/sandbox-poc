# Local Application Testing

This guide covers running and testing the application on Windows with PowerShell.
It does not deploy the hosting infrastructure or change the existing theme.
Use the [customer deployment guide](customer-deployment.md) for Azure hosting.

## 1. Choose A Test Mode

| Mode | Worker | Purpose |
| --- | --- | --- |
| UI/API only | Stopped | Test sign-in, configuration, requests and approval decisions; approved operations remain queued |
| Local simulation | Running with `TERRAFORM_ENABLED=false` | Test workflow status changes without creating or deleting Azure resources |
| Real Azure integration | Running with `TERRAFORM_ENABLED=true` | Test actual provisioning, scoped access, policy, budget and approved cleanup in a disposable environment |

**Local hosting does not mean local infrastructure.** A local worker configured
for Azure can create, update and delete real resources, send email, and incur
charges. Stop all workers using a shared test database before changing modes.
Use separate databases, runtime directories and Terraform state keys for separate
environments. Do not copy production data into a simulation environment.

`python -m app.worker --once` is not a dry run: it can execute an approved operation
and perform lifecycle/email maintenance. Do not use it to test startup against
production data.

## 2. Prerequisites

- Python 3.12 and Node.js 24 LTS with npm.
- An Entra SPA/API registration configured for local testing, API scope consent,
  and two test accounts: an ordinary requestor and a different administrator.
- The administrator must have the API application role configured by `ADMIN_ROLE`,
  normally `Sandboxadmin`. An Azure subscription role alone does not grant portal
  administrator access.
- Terraform and Azure authentication are needed only for real provisioning tests.
  Docker is optional for the ordinary local startup steps.

Open PowerShell in the repository root, containing Backend, Frontend and Terraform.
Commands below identify when to change directories. Paths are relative so they
also work when the repository folder contains spaces.

Create the backend environment only if it does not already exist:

```powershell
if (-not (Test-Path .\Backend\venv\Scripts\python.exe)) {
    py -3.12 -m venv .\Backend\venv
}
& .\Backend\venv\Scripts\python.exe -m pip install -r .\Backend\requirements.txt
npm --prefix Frontend ci
```

Use the same interpreter for API, worker and backend checks. These commands do
not require activating the environment or changing PowerShell execution policy.

## 3. Configure Local Settings

The templates are [Backend/.env.example](../Backend/.env.example) and
[Frontend/.env.example](../Frontend/.env.example). Existing local environment files
may contain real credentials and must not be overwritten. For a new checkout only:

```powershell
if (-not (Test-Path .\Backend\.env)) {
    Copy-Item .\Backend\.env.example .\Backend\.env
}
if (-not (Test-Path .\Frontend\.env)) {
    Copy-Item .\Frontend\.env.example .\Frontend\.env
}
```

Keep secrets in ignored backend settings or approved secret storage, never in the
frontend, documentation, terminal output or source control. URL-encode reserved
characters in connection credentials. When using an existing hosted database,
require TLS and verify firewall/network access; do not replace its connection
with the simulation example unless you intentionally want an isolated database.

### Isolated Simulation Settings

For a separate local simulation, configure Backend/.env with:

```dotenv
APP_ENV=development
DEBUG=false
DATABASE_URL=sqlite:///data/local-testing/platform.db
RUNTIME_DIRECTORY=data/local-testing
CORS_ORIGINS=["http://localhost:3000"]
TERRAFORM_ENABLED=false
COST_MANAGEMENT_ENABLED=false
MAX_SANDBOX_BUDGET=500
ALLOWED_SANDBOX_ROLES=["Owner","Contributor"]
ALLOW_OWNER_ROLE_REQUESTS=true
BUSINESS_UNIT_CATALOG_REQUIRED=true
COST_CENTER_MODE=business_unit
EXPIRY_GRACE_DAYS=7
```

Leave ACS sender, endpoint and connection-string settings unset in a simulation
that must not send email. Disabling Terraform does not disable email or cost
queries; they are separate services. Entra authentication is still real and needs
network access. Simulation does not test Azure permissions, actual resource
creation, billing, policy compliance or delivered email.

Configure the real test registration details in the backend:

| Setting | Local Value |
| --- | --- |
| `ENTRA_TENANT_ID` | Test tenant GUID |
| `ENTRA_API_AUDIENCE` | Exact audience of the API access token |
| `ENTRA_REQUIRED_SCOPE` | Exposed delegated scope name, commonly `access_as_user` |
| `ENTRA_ALLOWED_CLIENT_IDS` | JSON array containing the SPA client GUID |
| `ADMIN_ROLE` | API administrator role, normally `Sandboxadmin` |
| `AZURE_SUBSCRIPTION_ID` | Intended sandbox subscription; simulation resource links do not prove resources exist |
| `BUDGET_CURRENCY` | Actual configured billing currency; no currency conversion is performed |

Configure Frontend/.env:

```dotenv
NEXT_PUBLIC_CLIENT_ID=<SPA-CLIENT-GUID>
NEXT_PUBLIC_TENANT_ID=<TEST-TENANT-GUID>
NEXT_PUBLIC_REDIRECT_URI=http://localhost:3000/login
NEXT_PUBLIC_API_SCOPE=<FULL-EXPOSED-API-SCOPE-URI>
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Replace the placeholders. Register `http://localhost:3000/login` exactly as a SPA
redirect URI in Entra. The API base URL must not include `/api/v1`.
Use `localhost:3000` consistently for the frontend; do not substitute another
hostname or port without updating the redirect registration and CORS settings.

## 4. Start The API

In terminal 1, starting from the repository root:

```powershell
Set-Location .\Backend
& .\venv\Scripts\python.exe -m app.db.database init
& .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Initialize only the intended test database. Initialization creates missing tables;
it does not import JSON inventory or reconcile Terraform state. Do not run imports
against an existing environment merely to test startup.

The API is at http://127.0.0.1:8000. In development mode, interactive API
documentation is available at http://127.0.0.1:8000/docs. The API does not start
Terraform or the worker automatically.

## 5. Start The Frontend

In terminal 2, starting from the repository root:

```powershell
Set-Location .\Frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open http://localhost:3000/login. For production-mode testing, replace the last
command with:

```powershell
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

Public frontend settings are embedded at build time. Rebuild production output
after changing them; changing a runtime setting does not rewrite an old bundle.

## 6. Start The Worker When Required

For UI/API-only testing, leave the worker stopped. Approved jobs will wait.

For simulation, confirm the isolated database and disabled cloud services first.
Then, in terminal 3, starting from the repository root:

```powershell
Set-Location .\Backend
& .\venv\Scripts\python.exe -m app.worker
```

API and worker must run from Backend and use the same environment/database. This
also keeps relative simulation database paths consistent. Do not use automatic
worker reload or start additional copies to work around an active job.

In terminal 4, check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ready
```

Expected: API responds and database is `ready`. With a running worker, its status
is `ready`; in development, `not_running` is expected for UI/API-only mode.
Heartbeat health alone does not prove that Azure permissions or provisioning work.

## 7. Configure Local Test Data

1. Sign in as the administrator and open Admin > Business units.
2. Add a clearly identified local test company, a unique short code such as `TST`,
   and a test cost centre. Save it as active. Do not invent Harris production data.
3. Confirm the unit appears in the list and that duplicate names/codes are rejected.
4. For bulk testing, use the JSON format in the customer deployment guide, including
   `name`, `shortCode`, `costCenters` and `active` for every entry.
5. Open Admin > Settings to view the current platform-wide sandbox subscription.
   Listing subscriptions requires Azure read access for the configured backend
   identity, even when provisioning is simulated. Do not switch a shared environment
   for an ordinary UI test. Active work or nonempty Terraform state blocks changes.

## 8. Manual Workflow Checklist

Use separate browser profiles, or sign out and change accounts, to test the
requestor and administrator. The application rejects self-approval.

| Test | Expected Result |
| --- | --- |
| Open an admin page while signed out or as an ordinary user | Sign-in redirect or access denial |
| Submit without a business unit, linked cost centre or manager email | Validation error; no request accepted |
| Request a budget below/at the maximum | Accepted for approval |
| Request or approve a budget above the maximum | Rejected by the API |
| Select Contributor or Owner | Request records the selected resource-group role; Contributor is the default |
| Preview a test unit with short code `TST` | New name begins `rg-sandbox-tst-`; existing resource names do not change |
| Submit as requestor; approve as a different admin | Status becomes Provisioning, then Active after the worker succeeds |
| Reject a request with a reason | Request shows Rejected and retains its reason/history |
| Request an extension by duration or future date | Extension waits for admin approval; bounds are validated |
| Approve an extension | Desired expiry is recorded; applied expiry changes after successful worker completion |
| Flag cleanup for an expired test sandbox | Cleanup waits for the configured grace period and admin flag |
| Leave a sandbox expired but unflagged | No automatic resource deletion; real resources continue charging |
| Submit a pending extension for flagged cleanup | Cleanup is blocked; approving the extension cancels earlier flags |
| Inspect notifications | Decisions/lifecycle messages are persisted; email is only delivered if configured |
| Inspect costs without a successful billing query | Unavailable, not fabricated spending |

Simulation marks operations successful without creating resources. A simulated
Active/Decommissioned status is not evidence that an Azure resource exists or was
deleted. Test elapsed-time expiry/grace logic with the automated tests below, not
by changing a real database date or shortening a shared environment's grace period.

## 9. Real Azure Integration Testing

Only enable this mode after reviewing the target subscription, identity permissions,
dedicated database, state storage and queued operations. Use disposable resources.

- Set `TERRAFORM_ENABLED=true` in the API and worker configuration and install
  Terraform on the worker machine.
- Local testing normally uses a service principal via `ARM_CLIENT_ID`,
  `ARM_TENANT_ID` and secret storage, with `ARM_USE_MSI=false`. Alternatively, use an
  approved local Azure CLI identity where supported. Managed identity requires an
  Azure host exposing that identity; it is not supplied by an ordinary local PC.
- Configure all `TERRAFORM_STATE_*` values and verify the backend matches the test
  state. Never reuse production state for simulation or unrelated test resources.
- Verify resource creation/deletion, scoped role assignment, budgets, policy and
  state-container access. The original six-tag Audit policy is assigned only to each
  sandbox resource group; it does not block deployments or enforce region rules.
- Enable real cost collection only with the required billing read permissions.
  Fetches are cached hourly by default, and Azure billing data can be delayed.
- Configure verified ACS details and approved recipients for email tests. Check
  both owner delivery and administrator CC; native budget emails use a recipient
  list rather than a CC field.

Starting the worker can execute already-approved jobs immediately. Do not retry a
failed operation until its error is understood. Keep `prevent_destroy`, saved-plan
review and deletion/replacement checks enabled. Use approved cleanup for disposable
resources; do not manually delete state entries to make an error disappear.

## 10. Automated Checks

From the repository root, with the backend environment installed:

```powershell
if ($env:TEST_DATABASE_URL) {
    throw 'Unset TEST_DATABASE_URL for the default isolated test run.'
}
& .\Backend\venv\Scripts\python.exe -m pytest Backend/tests -q
& .\Backend\venv\Scripts\python.exe -m ruff check Backend/app Backend/tests
npm --prefix Frontend run lint
npm --prefix Frontend run build
terraform -chdir=Terraform/environments/dev validate -no-color
terraform -chdir=Terraform/environments/dev test -test-directory=tests -no-color
```

Backend tests use temporary isolated storage and mocked cloud operations. The
Terraform test uses a mock Azure provider and does not apply real resources.
Dedicated database integration testing is documented in Backend/README.md; those
tests clear the designated test records, so never point them at application data.

## 11. Troubleshooting

| Symptom | Check |
| --- | --- |
| Startup exits with address already in use | A server may already be running. Identify its process before stopping it; do not launch repeated copies |
| Frontend cannot reach the API | API listener, `NEXT_PUBLIC_API_BASE_URL`, CORS origin, and rebuilt public settings |
| Entra redirect mismatch | Exact registered `http://localhost:3000/login` URI and correct SPA tenant/client |
| API returns 401/403 | API audience, v2 token, delegated scope, consent, client allowlist and API administrator role |
| No business units/cost centres available | Admin catalogue setup, active status, short codes and the configured cost-centre mode |
| Approval stays Provisioning | Worker stopped/unhealthy, mismatched database settings, or worker logs |
| Costs unavailable | Active resource, billing permissions, refresh timing, worker logs and Azure billing latency |
| Instance cannot be destroyed | Inventory/state mismatch or destructive plan; preserve/reconcile existing resources, never disable the safeguard |
| Moved resource instances excluded by targeting | Use the current worker, which includes the shared policy migration target; restart an old worker before retrying |
| Terraform state is locked | Confirm no worker/apply is active before a reviewed recovery; never force-unlock blindly |

To inspect listeners without changing them:

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @(3000, 8000) } |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Detailed operation logs are in the configured runtime directory's `logs` folder.
Treat them as private. Use Ctrl+C to stop each local process after testing; allow
running provisioning to finish before stopping the worker. Before restarting,
check that no duplicate listeners/workers remain. Stopping local processes does
not stop billing for Azure resources that already exist.