# Hosting Deployment

| Setting | Value |
| --- | --- |
| Subscription | `7e76e808-906f-46c5-9a79-d35cee8a9bb4` |
| Resource group | `RG-SANDBOX-DEV` |
| Region | `centralindia` |

[main.bicep](main.bicep) deploys into an existing resource group. Use
`--subscription 7e76e808-906f-46c5-9a79-d35cee8a9bb4 --resource-group RG-SANDBOX-DEV`
with `az deployment group validate`, `what-if`, and `create`.

This target replaces the earlier `rg-sandbox-platform-dev` proposal. Keep hosting
resources separate from the sandbox provisioning configuration and remote state.
Recording this target does not create resources or start the provisioning worker.

## Customer Handover

The [customer-run deployment guide](../../docs/customer-deployment.md) describes
tenant prerequisites, configuration, preview-first deployment, image publishing,
worker setup and acceptance checks. [deploy.ps1](deploy.ps1) runs under the
customer's own Azure login and does not require delivery-team guest access.
Customer deployment parameters must be supplied explicitly; local development
subscription and application IDs are not template defaults.