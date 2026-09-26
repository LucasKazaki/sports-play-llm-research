$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$required = @('pytest','cv2','numpy','imageio_ffmpeg','onnxruntime','chess','requests','zstandard')
$checks = @()
try {
  $python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules $required
  $checks += [ordered]@{ name = 'python-dependencies'; passed = $true; evidence = "$python ($($required -join ', '))" }
} catch {
  $python = $null
  $checks += [ordered]@{ name = 'python-dependencies'; passed = $false; evidence = $_.Exception.Message }
}
foreach ($file in @(
  'README.md','PROJECT_GUIDE.md','AGENTS.md','requirements-windows-py311.lock.txt',
  'scripts\reproduce.ps1','scripts\resolve-python.ps1','scripts\github_sync_audit.py',
  'footballmaster\__main__.py','prototype\sports_play_lab.py','tests\test_sports_play_lab.py'
)) {
  $checks += [ordered]@{ name = "file:$file"; passed = (Test-Path -LiteralPath (Join-Path $root $file)); evidence = $file }
}
$passed = -not ($checks | Where-Object { -not $_.passed })
$summary = [ordered]@{ schemaVersion = 1; passed = $passed; portableCheckout = $true; checks = $checks }
$summary | ConvertTo-Json -Depth 5 -Compress
if (-not $passed) { exit 1 }
