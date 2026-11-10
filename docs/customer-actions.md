# Customer Decisions And Action Items

## Agreed Scope

- Keep the existing theme, colours, typography and layout. Branding/style changes
  and self-service portal embedding are separate follow-ups, not implemented here.
- Retain Entra SSO, independent administrator approval and resource-group sandboxes
  inside a shared subscription. No programmatic subscription creation is added.
- Provide configurable budget limits, business-unit/cost-centre data, administrator
  alert copies, expiry reminders, extensions and administrator-flagged cleanup.
- Harris administrators execute the deployment materials; external guest access
  for the delivery team is not required.

## Inputs Required From Harris

| Decision | Owner | Status |
| --- | --- | --- |
| Business-unit/company master list, approximately 400 companies | Noah / Harris | Pending; no Harris data invented |
| Whether cost centres are per company, shared, or free text | Noah / Harris | Pending; configurable modes provided |
| Maximum budget and actual subscription billing currency | Noah / Harris | Pending; default maximum 500 in configured currency |
| Approved resource-group roles, including whether Owner is permitted | Harris security / Noah | Pending; Owner requires explicit opt-in |
| Allowed regions and any future governance changes | Noah / Harris governance / Vimal | Pending; original resource-group Audit policy retained as subsequently requested |
| Administrator/distribution emails and manager notification requirements | Noah / Harris | Pending; recipient configuration provided |
| Grace period, reminder timing and maximum extension | Noah / Kesavan / Harris | Pending; example defaults are not customer sign-off |
| Hosting/network access, Entra registration/consent and worker identity | Harris administrators | Pending customer-tenant configuration review |

## Delivery Changes

| Change | Status |
| --- | --- |
| Configurable budget maximum on requests and approvals | Implemented; lower amounts allowed |
| Backend-driven form options and manager tag | Implemented |
| Admin business-unit maintenance and bulk JSON import | Implemented; import/update supports the expected company scale |
| Budget administrators as application-email CC and native budget contacts | Implemented; actual sender/addresses need configuration |
| Grace period, user/manager/admin reminders and explicit cleanup flag | Implemented; no unapproved expiry deletion |
| Extension by configured duration or requested future expiry | Implemented; approved extensions cancel old cleanup flags |
| Policy placement | Original six-tag Audit policy assigned only to sandbox resource groups |
| Customer-run hosting/publishing script and sequenced guide | Provided in infra/hosting and customer-deployment.md |
| Branding changes | Excluded as requested |

## Meeting Follow-Up Draft

To: meeting participants, to be supplied by Srividya

Subject: Azure Sandbox review - decisions and required Harris inputs

The demonstrated request/approval and resource-group model remains the initial
operating model. The functionality follow-up covers configurable budget limits,
business-unit/cost-centre management, administrator alert copies and an expiry
workflow with grace, extensions and explicit administrator cleanup approval.

Harris is requested to confirm the master data, cost-centre relationship, currency
and maximum budget, approved roles/regions, policy placement, notification recipients,
grace period and extension rules. Delivery will provide the code, scripts and
deployment prerequisites for Harris administrators to execute and review in their
tenant without external guest onboarding. The current theme remains unchanged.

Srividya owns consolidation and circulation. Vimal/Kesavan own technical follow-up;
Noah/Harris own the operating inputs and tenant review. This is a draft handover
record, not an email that has been sent and not a customer production sign-off.