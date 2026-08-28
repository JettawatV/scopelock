[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$adk = Join-Path $repoRoot ".venv313\Scripts\adk.exe"
$reportPath = Join-Path $repoRoot "artifacts\evals\pre-gmail-live-gate.json"

if (-not (Test-Path -LiteralPath $adk)) {
    throw "ADK executable not found at $adk"
}

$runs = @()
$requirements = (
    "tests\eval\requirement_analyzer.evalset.json:" +
    "golden_initial_request,mixed_supported_and_unsupported," +
    "thai_supported_request,deadline_constraint,prompt_injection_request"
)
$scope = "tests\eval\scope_analyzer.evalset.json:E028"
$requirementAgent = "tests\live_agents\requirement_app"
$scopeAgent = "tests\live_agents\scope_app"

function Invoke-ReviewedEval {
    param(
        [string]$EvalSelector,
        [string]$AgentPath,
        [string]$ConfigPath,
        [string]$ResultPattern,
        [int]$ExpectedCases,
        [int]$Iteration
    )

    & $adk eval $AgentPath $EvalSelector --config_file_path $ConfigPath | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Live ADK command failed for $EvalSelector on iteration $Iteration"
    }
    $agentHistory = Join-Path $repoRoot "$AgentPath\.adk\eval_history"
    $result = Get-ChildItem -LiteralPath $agentHistory -Filter "*$ResultPattern*.evalset_result.json" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $result) {
        throw "ADK did not write an eval result for $ResultPattern"
    }
    $payload = Get-Content -Raw -LiteralPath $result.FullName | ConvertFrom-Json
    $cases = @($payload.eval_case_results)
    if ($cases.Count -ne $ExpectedCases) {
        throw "Expected $ExpectedCases cases for $ResultPattern; found $($cases.Count)"
    }
    $failed = @($cases | Where-Object { $_.final_eval_status -ne 1 })
    if ($failed.Count -gt 0) {
        $failedIds = ($failed | ForEach-Object { $_.eval_id }) -join ", "
        throw "Live ADK review gate failed on iteration ${Iteration}: $failedIds"
    }
    return [pscustomobject]@{
        iteration = $Iteration
        eval_set = $ResultPattern
        cases = $cases.Count
        passed = $cases.Count
        failed = 0
        result_file = $result.Name
    }
}

Push-Location -LiteralPath $repoRoot
try {
    foreach ($iteration in 1..3) {
        $runs += Invoke-ReviewedEval `
            -EvalSelector $requirements `
            -AgentPath $requirementAgent `
            -ConfigPath "tests\eval\requirement_analyzer.config.json" `
            -ResultPattern "scopelock_requirement_analyzer_v5" `
            -ExpectedCases 5 `
            -Iteration $iteration
        $runs += Invoke-ReviewedEval `
            -EvalSelector $scope `
            -AgentPath $scopeAgent `
            -ConfigPath "tests\eval\scope_analyzer.config.json" `
            -ResultPattern "scopelock_scope_analyzer_v3" `
            -ExpectedCases 1 `
            -Iteration $iteration
    }

    $report = [ordered]@{
        gate = "pre_gmail_flexibility_live_repeatability"
        prompt_versions = @(
            "requirement_analyzer_v5",
            "scope_analyzer_v3"
        )
        expected_runs = 18
        passed_runs = ($runs | Measure-Object -Property passed -Sum).Sum
        failed_runs = 0
        runs = $runs
    }
    $reportDirectory = Split-Path -Parent $reportPath
    New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
    $report | ConvertTo-Json -Depth 8
}
finally {
    Pop-Location
}
