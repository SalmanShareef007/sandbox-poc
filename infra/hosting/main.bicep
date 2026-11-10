targetScope = 'resourceGroup'

param location string = resourceGroup().location
param suffix string
param imageTag string
param deployerPrincipalId string
param entraTenantId string
param entraClientId string
param apiAudience string
param apiScope string = 'access_as_user'
param sandboxSubscriptionId string
@minValue(1)
param maxSandboxBudget int = 500
param budgetCurrency string = 'INR'
@minValue(0)
@maxValue(365)
param expiryGraceDays int = 7
@maxLength(4)
param adminNotificationEmails array = []
@allowed(['business_unit', 'shared', 'free_text'])
param costCenterMode string = 'business_unit'
param allowedRegions array = ['Central India']
param allowedRoles array = ['Owner', 'Contributor']
param allowOwnerRoleRequests bool = true

var tags = {
  Application: 'Azure Sandbox Platform'
  Environment: 'dev'
  ManagedBy: 'Bicep'
}

module apiIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'api-identity'
  params: {
    name: 'id-sbx-api-dev-${suffix}'
    location: location
    tags: tags
  }
}

module uiIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'ui-identity'
  params: {
    name: 'id-sbx-ui-dev-${suffix}'
    location: location
    tags: tags
  }
}

module registry 'br/public:avm/res/container-registry/registry:0.13.1' = {
  name: 'registry'
  params: {
    name: 'acrsbxdev${suffix}'
    location: location
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    roleAssignmentMode: 'LegacyRegistryPermissions'
    publicNetworkAccess: 'Enabled'
    networkRuleSetDefaultAction: 'Allow'
    tags: tags
    roleAssignments: [
      {
        principalId: apiIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'AcrPull'
      }
      {
        principalId: uiIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'AcrPull'
      }
    ]
  }
}

module vault 'br/public:avm/res/key-vault/vault:0.14.2' = {
  name: 'vault'
  params: {
    name: 'kv-sbx-dev-${suffix}'
    location: location
    sku: 'standard'
    enableRbacAuthorization: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    tags: tags
    roleAssignments: [
      {
        principalId: apiIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Key Vault Secrets User'
      }
      {
        principalId: deployerPrincipalId
        principalType: 'User'
        roleDefinitionIdOrName: 'Key Vault Secrets Officer'
      }
    ]
  }
}

module plan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'plan'
  params: {
    name: 'asp-sbx-dev-${suffix}'
    location: location
    skuName: 'B1'
    skuCapacity: 1
    reserved: true
    zoneRedundant: false
    tags: tags
  }
}

module ui 'br/public:avm/res/web/site:0.24.0' = {
  name: 'ui'
  params: {
    name: 'app-sbx-ui-dev-${suffix}'
    location: location
    kind: 'app,linux,container'
    serverFarmResourceId: plan.outputs.resourceId
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    tags: tags
    managedIdentities: {
      userAssignedResourceIds: [uiIdentity.outputs.resourceId]
    }
    siteConfig: {
      alwaysOn: true
      linuxFxVersion: 'DOCKER|${registry.outputs.loginServer}/sandbox-ui:${imageTag}'
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: uiIdentity.outputs.clientId
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/login'
    }
    basicPublishingCredentialsPolicies: [
      { name: 'ftp', allow: false, location: location }
      { name: 'scm', allow: false, location: location }
    ]
    configs: [
      {
        name: 'appsettings'
        properties: {
          WEBSITES_PORT: '3000'
          WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
          NODE_ENV: 'production'
        }
      }
    ]
  }
}

module api 'br/public:avm/res/web/site:0.24.0' = {
  name: 'api'
  params: {
    name: 'app-sbx-api-dev-${suffix}'
    location: location
    kind: 'app,linux,container'
    serverFarmResourceId: plan.outputs.resourceId
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    tags: tags
    managedIdentities: {
      userAssignedResourceIds: [apiIdentity.outputs.resourceId]
    }
    keyVaultAccessIdentityResourceId: apiIdentity.outputs.resourceId
    siteConfig: {
      alwaysOn: true
      linuxFxVersion: 'DOCKER|${registry.outputs.loginServer}/sandbox-api:${imageTag}'
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: apiIdentity.outputs.clientId
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/api/v1/health'
    }
    basicPublishingCredentialsPolicies: [
      { name: 'ftp', allow: false, location: location }
      { name: 'scm', allow: false, location: location }
    ]
    configs: [
      {
        name: 'appsettings'
        properties: {
          WEBSITES_PORT: '8000'
          WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
          APP_ENV: 'production'
          DEBUG: 'false'
          DATABASE_URL: '@Microsoft.KeyVault(SecretUri=${vault.outputs.uri}secrets/database-url)'
          ENTRA_TENANT_ID: entraTenantId
          ENTRA_API_AUDIENCE: apiAudience
          ENTRA_REQUIRED_SCOPE: apiScope
          ENTRA_ALLOWED_CLIENT_IDS: string([entraClientId])
          ALLOWED_SANDBOX_ROLES: string(allowedRoles)
          ALLOW_OWNER_ROLE_REQUESTS: string(allowOwnerRoleRequests)
          MAX_SANDBOX_BUDGET: string(maxSandboxBudget)
          BUDGET_CURRENCY: budgetCurrency
          EXPIRY_GRACE_DAYS: string(expiryGraceDays)
          ADMIN_NOTIFICATION_EMAILS: string(adminNotificationEmails)
          COST_CENTER_MODE: costCenterMode
          BUSINESS_UNIT_CATALOG_REQUIRED: 'true'
          ALLOWED_REGIONS: string(allowedRegions)
          AZURE_SUBSCRIPTION_ID: sandboxSubscriptionId
          CORS_ORIGINS: string(['https://${ui.outputs.defaultHostname}'])
        }
      }
    ]
  }
}

output apiUrl string = 'https://${api.outputs.defaultHostname}'
output uiUrl string = 'https://${ui.outputs.defaultHostname}'
output apiName string = api.outputs.name
output uiName string = ui.outputs.name
output registryName string = registry.outputs.name
output registryLoginServer string = registry.outputs.loginServer
output vaultName string = vault.outputs.name
output vaultUri string = vault.outputs.uri
output apiIdentityId string = apiIdentity.outputs.resourceId
output imageTag string = imageTag