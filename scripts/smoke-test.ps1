$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules @('pytest','cv2','numpy')
$outputRoot = [System.IO.Path]::GetFullPath((Join-Path $root 'artifacts\autonomy-smoke'))
if (-not $outputRoot.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe smoke output directory.' }
Push-Location $root
try {
  & $python prototype/sports_play_lab.py demo --out $outputRoot
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  foreach ($evidence in @('prediction.json','metrics.json','receipt.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $outputRoot $evidence))) { throw "Synthetic smoke evidence was not created: $evidence" }
  }
} finally {
  Pop-Location
}
