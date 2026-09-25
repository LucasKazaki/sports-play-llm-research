$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$checks = @()
try {
  $projectPython = Join-Path $root '.venv-soccernet\Scripts\python.exe'
  $python = $null
  if (Test-Path -LiteralPath $projectPython) {
    & $projectPython -c 'import pytest, cv2, numpy, imageio_ffmpeg, onnxruntime' *> $null
    if ($LASTEXITCODE -eq 0) { $python = $projectPython }
  }
  if (-not $python) {
    $python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules @('pytest','cv2','numpy','imageio_ffmpeg','onnxruntime')
  }
  $checks += [ordered]@{ name = 'python-development-dependencies'; passed = $true; evidence = "$python (pytest, cv2, numpy, imageio_ffmpeg, onnxruntime)" }
} catch {
  $python = $null
  $checks += [ordered]@{ name = 'python'; passed = $false; evidence = $_.Exception.Message }
}
foreach ($file in @(
  'prototype\sports_play_lab.py','prototype\playground-output.schema.json','tests\test_sports_play_lab.py','state\loop-state.json',
  'prototype\footballmaster_pilot.py','tests\test_footballmaster_pilot.py','data\public\footballmaster\source-manifest.json',
  'data\public\footballmaster\examples.jsonl','artifacts\footballmaster\pilot-v1\run-receipt.json',
  'footballmaster\__main__.py','footballmaster\pipeline.py','footballmaster\config.py','footballmaster\schema.py',
  'footballmaster\search.py','footballmaster\resources\default-config.json','footballmaster\schemas\model-card.schema.json',
  'tests\test_footballmaster_isolation.py'
)) {
  $checks += [ordered]@{ name = "file:$file"; passed = (Test-Path -LiteralPath (Join-Path $root $file)); evidence = (Join-Path $root $file) }
}
$passed = -not ($checks | Where-Object { -not $_.passed })
$summary = [ordered]@{ schemaVersion = 1; passed = $passed; checks = $checks; generatedAt = (Get-Date).ToUniversalTime().ToString('o') }
$output = Join-Path $root 'artifacts\autonomy-doctor.json'
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $output -Encoding utf8
$summary | ConvertTo-Json -Depth 6 -Compress
if (-not $passed) { exit 1 }
