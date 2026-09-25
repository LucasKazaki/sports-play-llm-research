$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectPython = Join-Path $root '.venv-soccernet\Scripts\python.exe'
$python = $null
if (Test-Path -LiteralPath $projectPython) {
  & $projectPython -c 'import pytest, cv2, numpy, imageio_ffmpeg, onnxruntime' *> $null
  if ($LASTEXITCODE -eq 0) { $python = $projectPython }
}
if (-not $python) {
  $python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules @('pytest','cv2','numpy','imageio_ffmpeg','onnxruntime')
}
$steps = @()
function Run([string]$Name, [string[]]$Arguments) {
  & $python @Arguments
  $code = $LASTEXITCODE
  $script:steps += [ordered]@{ name = $Name; command = "python $($Arguments -join ' ')"; exitCode = $code }
  if ($code -ne 0) { throw "$Name failed with exit $code" }
}
Push-Location $root
try {
  Run 'compile' @('-m','compileall','-q','footballmaster','prototype','tests')
  Run 'tests' @('-m','pytest','-q')
  $summary = [ordered]@{ schemaVersion = 1; passed = $true; realDataClaims = 'FootballMaster package remains descriptive-only with performanceClaimAllowed=false'; externalActions = @(); steps = $steps; generatedAt = (Get-Date).ToUniversalTime().ToString('o') }
} catch {
  $summary = [ordered]@{ schemaVersion = 1; passed = $false; steps = $steps; error = $_.Exception.Message; generatedAt = (Get-Date).ToUniversalTime().ToString('o') }
} finally { Pop-Location }
$output = Join-Path $root 'artifacts\autonomy-verification.json'
$summary | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $output -Encoding utf8
$summary | ConvertTo-Json -Depth 7 -Compress
if (-not $summary.passed) { exit 1 }
