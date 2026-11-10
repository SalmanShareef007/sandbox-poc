[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9]{4,10}$')][string]$Suffix,
    [Parameter(Mandatory)][string]$EntraTenantId,
    [Parameter(Mandatory)][string]$SpaClientId,
    [Parameter(Mandatory)][string]$ApiAudience,
    [Parameter(Mandatory)][string]$ApiScopeUri,
    [Parameter(Mandatory)][string]$SandboxSubscriptionId,
    [Parameter(Mandatory)][ValidatePattern('^[A-Z]{3}$')][string]$BudgetCurrency,
    [Parameter(Mandatory)][ValidateRange(0,365)][int]$ExpiryGraceDays,
    [Parameter(Mandatory)][ValidateCount(1,4)][string[]]$AdminNotificationEmails,
    [Parameter(Mandatory)][string[]]$AllowedRegions,
    [ValidateSet('business_unit','shared','free_text')][string]$CostCenterMode = 'business_unit',
    [ValidateRange(1,100000000)][int]$MaxSandboxBudget = 500,
    [string]$Location,
    [string]$ImageTag = (Get-Date -Format 'yyyyMMddHHmmss'),
    [string]$DeployerPrincipalId,
    [string]$DatabaseConnectionFile,
    [switch]$Apply,
    [switch]$DeployApplication
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Invoke-Azure {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
    $result = & az @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Azure command failed: $($Arguments[0..1] -join ' ')" }
    return $result
}

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker build/publish failed.' }
}

if ($DeployApplication -and -not $Apply) { throw '-DeployApplication requires -Apply.' }
if ($DeployApplication -and -not $DatabaseConnectionFile) { throw 'Provide a restricted database connection file outside the repository.' }
if ($DatabaseConnectionFile) {
    $DatabaseConnectionFile = (Resolve-Path -LiteralPath $DatabaseConnectionFile).Path
    if ($DatabaseConnectionFile.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Keep the database connection file outside the repository.'
    }
}
Invoke-Azure @('account','set','--subscription',$SubscriptionId)
$group = Invoke-Azure @('group','show','--subscription',$SubscriptionId,'--name',$ResourceGroup,'--output','json') | ConvertFrom-Json
if (-not $Location) { $Location = $group.location }
if (-not $DeployerPrincipalId) { $DeployerPrincipalId = (Invoke-Azure @('ad','signed-in-user','show','--query','id','--output','tsv')).Trim() }
$settings = @{
    location = $Location; suffix = $Suffix; imageTag = $ImageTag
    deployerPrincipalId = $DeployerPrincipalId; entraTenantId = $EntraTenantId
    entraClientId = $SpaClientId; apiAudience = $ApiAudience
    apiScope = ($ApiScopeUri -split '/')[-1]; sandboxSubscriptionId = $SandboxSubscriptionId
    maxSandboxBudget = $MaxSandboxBudget; budgetCurrency = $BudgetCurrency
    expiryGraceDays = $ExpiryGraceDays; adminNotificationEmails = $AdminNotificationEmails
    allowedRegions = $AllowedRegions; costCenterMode = $CostCenterMode
}
$parameters = @{}
foreach ($key in $settings.Keys) { $parameters[$key] = @{ value = $settings[$key] } }
$file = [IO.Path]::GetTempFileName()
try {
    @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'; contentVersion = '1.0.0.0'; parameters = $parameters } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $file -Encoding utf8
    $common = @('--subscription',$SubscriptionId,'--resource-group',$ResourceGroup,'--template-file',(Join-Path $PSScriptRoot 'main.bicep'),'--parameters',"@$file")
    Invoke-Azure (@('deployment','group','validate') + $common + @('--query','properties.provisioningState','--output','tsv'))
    Invoke-Azure (@('deployment','group','what-if') + $common + @('--result-format','ResourceIdOnly'))
    if (-not $Apply) { Write-Output 'Preview only. Review costs and changes before using -Apply.'; return }
    $deploymentName = "sandbox-hosting-$ImageTag"
    Invoke-Azure (@('deployment','group','create','--name',$deploymentName,'--mode','Incremental') + $common + @('--query','properties.provisioningState','--output','tsv'))
    $outputs = Invoke-Azure @('deployment','group','show','--subscription',$SubscriptionId,'--resource-group',$ResourceGroup,'--name',$deploymentName,'--query','properties.outputs','--output','json') | ConvertFrom-Json
    Write-Output "Frontend: $($outputs.uiUrl.value)"
    Write-Output "API: $($outputs.apiUrl.value)"
    Write-Output "Register the SPA redirect URI: $($outputs.uiUrl.value)/login"
    if (-not $DeployApplication) { return }
    Invoke-Azure @('keyvault','secret','set','--subscription',$SubscriptionId,'--vault-name',$outputs.vaultName.value,'--name','database-url','--file',$DatabaseConnectionFile,'--query','id','--output','tsv') | Out-Null
    Invoke-Azure @('acr','login','--subscription',$SubscriptionId,'--name',$outputs.registryName.value)
    $registry = $outputs.registryLoginServer.value
    Invoke-Docker @('build','--platform','linux/amd64','-f',(Join-Path $repo 'Backend/Dockerfile'),'--target','api','-t',"${registry}/sandbox-api:$ImageTag",$repo)
    Invoke-Docker @('build','--platform','linux/amd64','-t',"${registry}/sandbox-ui:$ImageTag",'--build-arg',"NEXT_PUBLIC_CLIENT_ID=$SpaClientId",'--build-arg',"NEXT_PUBLIC_TENANT_ID=$EntraTenantId",'--build-arg',"NEXT_PUBLIC_REDIRECT_URI=$($outputs.uiUrl.value)/login",'--build-arg',"NEXT_PUBLIC_API_SCOPE=$ApiScopeUri",'--build-arg',"NEXT_PUBLIC_API_BASE_URL=$($outputs.apiUrl.value)",(Join-Path $repo 'Frontend'))
    Invoke-Docker @('push',"${registry}/sandbox-api:$ImageTag")
    Invoke-Docker @('push',"${registry}/sandbox-ui:$ImageTag")
    foreach ($app in @($outputs.apiName.value,$outputs.uiName.value)) {
        Invoke-Azure @('webapp','restart','--subscription',$SubscriptionId,'--resource-group',$ResourceGroup,'--name',$app)
    }
    Write-Output 'Images published. Verify HTTPS, sign-in, API liveness, and worker/database readiness before use.'
} finally {
    Remove-Item -LiteralPath $file -ErrorAction SilentlyContinue
}