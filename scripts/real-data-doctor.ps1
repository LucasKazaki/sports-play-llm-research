param(
    [string]$Model = "google/gemma-4-e4b",
    [string]$Endpoint = "http://127.0.0.1:1234/v1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-soccernet\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing isolated SoccerNet environment: $python"
}

& $python (Join-Path $projectRoot "prototype\real_data_doctor.py") --model $Model --endpoint $Endpoint
if ($LASTEXITCODE -ne 0) {
    throw "Real-data doctor failed. See artifacts\soccernet-pilot-v1\real-data-doctor.json"
}
