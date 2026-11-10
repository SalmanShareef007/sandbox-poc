# Customer-Run Deployment

Harris administrators run these steps in their own tenant. Delivery-team guest
access is not required. The existing application theme and branding are unchanged.
Do not treat the values in a local development environment as Harris production
configuration.

## 1. Confirm Operating Decisions

Complete the [customer action list](customer-actions.md) before enabling production
provisioning. Confirm the hosting subscription, sandbox subscription, billing
currency, maximum budget, allowed regions/roles, company list, cost-centre model,
manager requirements, alert recipients, grace period and extension limits.

The maximum defaults to 500 in the configured currency; it is not a currency
conversion and is not an Azure spending cap. The example seven-day grace period
is configurable, not a confirmed Harris decision. Cleanup always requires an
administrator flag; grace expiry alone never authorizes deletion.

## 2. Prepare Tenant Access And Tools

- Use a Harris-owned deployment account with access to the hosting resource group,
  resource creation permissions and scoped role-assignment permissions. Create the
  resource group separately with any Harris-required tags.
- Install PowerShell 7, Azure CLI with Bicep, Docker with Linux image support,
  Python 3.12 and Node.js 24. Build/test images and review vulnerability findings.
  Previously identified dependency vulnerabilities remain deferred in the current
  development build; Harris must approve their resolution or a documented test-only
  exception. Do not silently disable the CI scan gates.
- Arrange a supported application database, TLS connection details, initialization
  permissions, runtime permissions, backups and network access. Keep secrets outside
  source control. The hosting template does not create, migrate or relocate it.
- Use distinct environments for testing and production: database, state key,
  identities, hostnames and sandbox resources must not be shared unintentionally.

## 3. Configure Microsoft Entra ID

1. Register a single-tenant SPA and an API in the Harris tenant. Expose a delegated
   API scope such as `access_as_user`; configure the API to issue v2 access tokens.
2. Grant the SPA permission to that scope and obtain the required consent.
3. Define `Sandboxadmin` as an API application role and assign it to the approved
   administrator users or groups. Ordinary users do not receive that role.
4. Record the tenant ID, SPA client ID, exact API token audience and full scope URI.
   No SPA client secret is needed or permitted in frontend settings.
5. After hostnames are known, add the exact frontend HTTPS `/login` URL to the SPA's
   redirect URIs, retaining any separately approved existing redirects. Configure
   the corresponding logout behavior. Frontend and API role checks use the API's
   validated access-token claims, not an assumed ID-token role.

## 4. Initialize The Application Database

Using a restricted local environment and the intended initialization identity, set
`DATABASE_URL` securely and initialize once from Backend:

```powershell
python -m pip install -r requirements.txt
python -m app.db.database init
```

Review future schema changes as release migrations; application startup is not a
schema upgrade mechanism. Do not import sample inventory into production. Follow
the [migration and recovery guide](../Backend/README.md) for existing data/state.

## 5. Preview Hosting Infrastructure

Sign in directly with the approved Harris account:

```powershell
az login --tenant <HARRIS-TENANT-ID>
az account set --subscription <HOSTING-SUBSCRIPTION-ID>
```

From the repository root, prepare public deployment inputs:

```powershell
$deployment = @{
    SubscriptionId = '<HOSTING-SUBSCRIPTION-ID>'
    ResourceGroup = '<EXISTING-HOSTING-RESOURCE-GROUP>'
    Suffix = '<UNIQUE-LOWERCASE-SUFFIX>'
    EntraTenantId = '<HARRIS-TENANT-ID>'
    SpaClientId = '<SPA-CLIENT-ID>'
    ApiAudience = '<EXACT-API-TOKEN-AUDIENCE>'
    ApiScopeUri = '<FULL-DELEGATED-SCOPE-URI>'
    SandboxSubscriptionId = '<SANDBOX-SUBSCRIPTION-ID>'
    BudgetCurrency = '<THREE-LETTER-BILLING-CURRENCY>'
    MaxSandboxBudget = 500
    ExpiryGraceDays = 7
    AdminNotificationEmails = @('<APPROVED-ADMIN-EMAIL>')
    AllowedRegions = @('<APPROVED-AZURE-REGION-DISPLAY-NAME>')
    CostCenterMode = 'business_unit'
    ImageTag = '<RELEASE-TAG>'
}
./infra/hosting/deploy.ps1 @deployment
```

Replace every placeholder and confirm the currency/grace values. This defaults to
validation and what-if only. Review permissions, regional quota, network exposure,
names, proposed changes and current Azure prices. The template creates one shared
Linux B1 plan, two web apps, Basic registry, Key Vault and two web-app identities.
This is a development-sized public-endpoint topology, not a complete enterprise
private-network design. Have Harris review network isolation and sizing separately.

## 6. Provision And Publish

After approving costs and the preview:

```powershell
./infra/hosting/deploy.ps1 @deployment -Apply
```

Register the printed SPA redirect URI. Prepare a restricted UTF-8 file outside the
repository containing only the TLS-enabled database URL, without quotes or labels.
Do not send its contents in chat or commit it. The script uploads it directly to
Key Vault and does not print its value:

```powershell
./infra/hosting/deploy.ps1 @deployment -Apply -DeployApplication `
    -DatabaseConnectionFile '<RESTRICTED-FILE-OUTSIDE-REPOSITORY>'
```

The script selects the requested subscription, provisions incrementally, stores
the secret, builds/pushes the API and frontend images, and restarts the web apps.
Allow role-assignment propagation before secret upload or registry operations.
Images use the hosted API and redirect URLs at build time; rebuild when those
public settings change. This script does not deploy/start a worker or modify
Harris's app registration automatically.

## 7. Configure Business Data And Notifications

Sign in as an assigned administrator and open Business units. Add, edit or deactivate
units and their cost centres, or import a JSON array, up to 1,000 units per import:

```json
[
   { "name": "<APPROVED-COMPANY-NAME>", "shortCode": "FIN", "costCenters": ["<APPROVED-COST-CENTRE>"], "active": true }
]
```

Names are matched case-insensitively on import; existing matching units are updated,
not duplicated. An invalid batch is rejected transactionally. No sample Harris
companies are preloaded. `COST_CENTER_MODE` supports `business_unit`, `shared`, or
`free_text`; shared mode additionally requires `SHARED_COST_CENTERS` in API settings.

Each business unit has a unique short code of 1-12 letters/digits beginning with
a letter. Codes are normalized to lowercase and used in new sandbox names, for
example `rg-sandbox-fin-user-001`. Editing a code does not rename existing resources.
Legacy units without a stored code retain their earlier three-character prefix
until an administrator saves a reviewed code.

Admin Settings provides the platform-wide subscription dropdown, listing enabled
subscriptions accessible to the configured Azure identity. This is separate from
the hosting subscription and the developer's Azure CLI selection. The worker
validates changes; active requests/resources and nonempty Terraform state block
retargeting. Use a reviewed empty backend/state migration before selecting another
subscription. New requests are paused while a change is awaiting worker validation.
`TERRAFORM_STATE_SUBSCRIPTION_ID` identifies the subscription containing the state
storage account; it remains independent of the selected provisioning subscription.

Configure a verified ACS Email sender and either identity-based ACS access or a
Key Vault connection-string reference for the worker. Set
`ADMIN_NOTIFICATION_EMAILS` to approved recipients. Application budget/expiry email
uses explicit CC recipients. Native Azure budget notifications have a recipient
list, not a CC field; administrators are included as additional contacts. Use a
distribution address if more than four administrator contacts are needed.

## 8. Review Governance And Worker Identity

Use the reviewed Terraform configuration in Terraform/environments/dev or a
separate customer-owned environment. Keep hosting deployment and sandbox remote
state separate. Do not run applies against an unrelated state key.

The original policy audits the presence of Owner, BusinessUnit, CostCenter,
Environment, ExpiryDate and ManagedBy. It is assigned only to each sandbox resource
group, never at tenant, management-group or subscription scope. Azure stores its
reusable custom definition at subscription scope; this storage scope does not
apply the policy subscription-wide.

No additional Manager or allowed-location policy rules are added. Manager remains
part of the request and resource-group tags, and allowed regions are validated by
the application. Audit reports missing tags without blocking resource creation.
Keep the Terraform state-address migration and deletion safeguards enabled.

Request role options are Owner and Contributor; Contributor is selected by default.
Configure `ALLOWED_SANDBOX_ROLES` to restrict the options and remove Owner when
setting `ALLOW_OWNER_ROLE_REQUESTS=false`. Assignment remains resource-group-scoped.
Owner can delegate access and alter governance at that scope; inherited restrictions
and tenant governance still apply. Review custom-role creation permissions too.

## 9. Start A Separate Worker

Build the worker image from the repository root:

```powershell
docker build --platform linux/amd64 -f Backend/Dockerfile --target worker -t <REGISTRY>/sandbox-worker:<TAG> .
docker push <REGISTRY>/sandbox-worker:<TAG>
```

Run it on an approved always-running container host, independently of the web apps,
with at least one replica and no public ingress. Set the same application database
and business settings as the API, plus the state backend and approved governance
settings from Backend/.env.example. Do not use a transaction-pooling proxy: worker
coordination uses a database session lock. Avoid multiple environments sharing work.

Attach a dedicated managed identity, set `ARM_USE_MSI=true`, set its client ID for
a user-assigned identity, and omit service-principal secret settings. Grant scoped
resource provisioning/deletion, budget management, cost read, approved policy/RBAC
operations and state-container Blob Data Contributor permissions. Do not grant the
web apps these worker permissions. Local development may use a service principal.

Stop/drain the old worker before handover. Review queued jobs and existing remote
state/inventory before starting this worker: it can perform real Azure changes.
Email credentials and state storage access must be verified before acceptance.

## 10. Acceptance And Handover

Verify sign-in and denied access; catalogue and linked cost centres; manager tags;
budget below/at/above the limit; independent admin approval; actual provisioning;
scoped user access; costs; admin email copies; expiry reminders; grace timing;
extension approval and tag update; cancelled cleanup flags; and flagged deletion.
Use disposable test sandboxes, not customer production resources, for cleanup tests.

Check `/api/v1/health` for liveness and `/api/v1/ready` for database/worker readiness.
Enable monitoring, backups and alerting. Export audit logs to Harris's required
retention system. Keep admin-approved cleanup enabled; billing continues until
deletion actually finishes. Record tenant/configuration review and sign-off with
Harris before production rollout.