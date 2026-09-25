param(
    [string]$Query = 'shot save goalkeeper'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Resolve-ProjectPython -WorkspaceRoot $projectRoot -RequiredModules @('cv2','numpy')
$sampleRoot = Join-Path $projectRoot 'data\private\searchable-coaching-index-barca-bate-goal-30s-v2'
$database = Join-Path $sampleRoot 'search-index.sqlite3'
$receiptPath = Join-Path $sampleRoot 'run-receipt.json'
if (-not (Test-Path -LiteralPath $database)) {
    throw "Verified private coaching-search sample is missing: $database"
}
if (-not (Test-Path -LiteralPath $receiptPath)) {
    throw "Verified private coaching-search receipt is missing: $receiptPath"
}
$receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
$actualHash = (Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $receipt.database_sha256) { throw 'Private coaching-search database hash does not match its run receipt.' }
if ($receipt.audio_supplied_to_vlm -ne $false) { throw 'The verified demo is not visual-only.' }
if (@($receipt.failures_this_run).Count -ne 0 -or $receipt.indexed_event_count -lt 1) {
    throw 'The verified demo receipt is incomplete.'
}
Write-Host "Verified real SoccerNet systems sample: 30 s, $($receipt.indexed_event_count) indexed VLM events from 1 completed window report, audio not supplied."
Write-Warning 'UNADJUDICATED MODEL OUTPUT: this run demonstrates reporting and retrieval plumbing, not a correct coaching interpretation. Held-out SoccerNet labels show that this Gemma report contains confident event hallucinations.'
Push-Location $projectRoot
try {
    & $python prototype/searchable_match_vlm.py search --database $database --query $Query --limit 3 --compact
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
