$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectPython = Join-Path $root '.venv-soccernet\Scripts\python.exe'
if (Test-Path -LiteralPath $projectPython) {
  $python = $projectPython
} else {
  $python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules @('pytest')
}
Push-Location $root
try {
  & $python -m prototype.soccermaster_evidence_gated write-preregistration
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python -m prototype.soccermaster_evidence_gated write-private-binding-schema
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python -m prototype.soccermaster_evidence_gated dry-run
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python -m prototype.soccermaster_evidence_gated preflight
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}
