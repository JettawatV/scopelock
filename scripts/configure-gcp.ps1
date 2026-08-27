param(
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing $envPath. Copy .env.example to .env and set GOOGLE_CLOUD_PROJECT first."
}

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    $line = Get-Content -LiteralPath $envPath |
        Where-Object { $_ -match ('^\s*' + [regex]::Escape($Name) + '\s*=') } |
        Select-Object -First 1
    if (-not $line) {
        throw "$Name is missing from $envPath"
    }
    $value = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if (-not $value) {
        throw "$Name is empty in $envPath"
    }
    return $value
}

$projectId = Get-DotEnvValue -Name 'GOOGLE_CLOUD_PROJECT'
$vertexMode = Get-DotEnvValue -Name 'GOOGLE_GENAI_USE_VERTEXAI'

if ($vertexMode.ToLowerInvariant() -ne 'true') {
    throw 'GOOGLE_GENAI_USE_VERTEXAI must be true for the ScopeLock Vertex AI path.'
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw 'gcloud is not installed or is not available on PATH.'
}

Write-Host "ScopeLock Google Cloud project: $projectId"

if (-not $VerifyOnly) {
    & gcloud config set project $projectId
    if ($LASTEXITCODE -ne 0) { throw 'Failed to set the gcloud project.' }

    & gcloud services enable aiplatform.googleapis.com --project=$projectId
    if ($LASTEXITCODE -ne 0) { throw 'Failed to enable the Vertex AI / Agent Platform API.' }

    & gcloud auth application-default set-quota-project $projectId
    if ($LASTEXITCODE -ne 0) { throw 'Failed to set the ADC quota project.' }
}

$enabledService = & gcloud services list `
    --enabled `
    --project=$projectId `
    --filter='name:aiplatform.googleapis.com' `
    --format='value(name)'
if ($LASTEXITCODE -ne 0) { throw 'Failed to verify enabled Google Cloud services.' }

if ($enabledService -ne 'aiplatform.googleapis.com') {
    throw "aiplatform.googleapis.com is not enabled for $projectId."
}

Write-Host 'Vertex AI API is enabled and the project configuration is ready.'
