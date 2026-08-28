[CmdletBinding()]
param(
    [switch]$LiveAdk
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv313\Scripts\python.exe"
$adk = Join-Path $repoRoot ".venv313\Scripts\adk.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python 3.13 environment not found at $python"
}

Push-Location -LiteralPath $repoRoot
try {
    $baseTemp = Join-Path $repoRoot "artifacts\test-temp\agent-plan-$PID"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $baseTemp) | Out-Null
    & $python -m pytest -q --basetemp $baseTemp
    if ($LASTEXITCODE -ne 0) {
        throw "Deterministic agent-plan gate failed"
    }

    if ($LiveAdk) {
        if (-not (Test-Path -LiteralPath $adk)) {
            throw "ADK executable not found at $adk"
        }
        $evals = @(
            @("tests\eval\requirement_analyzer.evalset.json", "tests\eval\requirement_analyzer.config.json", "scopelock_requirement_analyzer_v4"),
            @("tests\eval\scope_analyzer.evalset.json", "tests\eval\scope_analyzer.config.json", "scopelock_scope_analyzer_v2"),
            @("tests\eval\workflow_trajectories.evalset.json", "tests\eval\workflow_trajectories.config.json", "scopelock_workflow_trajectories_v1")
        )
        foreach ($eval in $evals) {
            & $adk eval app $eval[0] --config_file_path $eval[1]
            if ($LASTEXITCODE -ne 0) {
                throw "Live ADK gate failed for $($eval[0])"
            }
            $result = Get-ChildItem -LiteralPath "app\.adk\eval_history" -Filter "*$($eval[2])*.evalset_result.json" |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($null -eq $result) {
                throw "ADK did not write an eval result for $($eval[2])"
            }
            $failedCases = @(
                (Get-Content -Raw -LiteralPath $result.FullName | ConvertFrom-Json).eval_case_results |
                    Where-Object { $_.final_eval_status -ne 1 }
            )
            if ($failedCases.Count -gt 0) {
                $failedIds = ($failedCases | ForEach-Object { $_.eval_id }) -join ", "
                throw "Live ADK semantic gate failed for $($eval[2]): $failedIds"
            }
        }
    }
}
finally {
    Pop-Location
}
