param(
    [int]$Port = 8771,
    [string]$Model = 'openai/gpt-oss-20b',
    [string]$Endpoint = 'http://127.0.0.1:1234/v1',
    [switch]$NoOpenBrowser,
    [switch]$LiteralQueryFallback
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectPython = Join-Path $projectRoot '.venv-soccernet\Scripts\python.exe'
$python = $null
if (Test-Path -LiteralPath $projectPython) {
    & $projectPython -c 'import cv2, numpy, imageio_ffmpeg, onnxruntime' *> $null
    if ($LASTEXITCODE -eq 0) {
        $python = $projectPython
    }
}
if (-not $python) {
    $python = Resolve-ProjectPython -WorkspaceRoot $projectRoot -RequiredModules @('cv2','numpy','imageio_ffmpeg','onnxruntime')
}
$demoUrl = "http://127.0.0.1:$Port/"
$healthUrl = "http://127.0.0.1:$Port/healthz"

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.ok -eq $true) {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status?sport=soccer" -TimeoutSec 3
        Write-Host "The coach-search UI is already running at $demoUrl"
        Write-Host "Existing soccer backend: $($status.backend); query mode: $($status.query_mode); model: $($status.query_model)"
        if (-not $LiteralQueryFallback -and $status.query_mode -ne 'local_query_llm') {
            Write-Warning 'This existing session uses literal search. It does not exercise the requested local query model. Stop the existing demo before restarting in model mode.'
        }
        if (-not $NoOpenBrowser) {
            Start-Process $demoUrl
        }
        exit 0
    }
} catch {
    # No healthy existing server; start the project-owned instance below.
}

Push-Location $projectRoot
try {
    Write-Host 'Starting the private PlayGround dual-sport coach-search UI...'
    Write-Warning 'Soccer prefers the verified 96-window complete-match index (90 dense minutes plus six stress windows) and is SYSTEMS GO / SEMANTIC NO-GO. FootballMaster prefers its sealed long-form test and is also semantic NO-GO. Older pilots are explicit fallback-only.'
    $serverArgs = @('prototype/multisport_search_demo_server.py', '--host', '127.0.0.1', '--port', $Port, '--model', $Model, '--endpoint', $Endpoint)
    if ($LiteralQueryFallback) {
        $serverArgs += '--literal-query-fallback'
    }
    if (-not $NoOpenBrowser) {
        $serverArgs += '--open-browser'
    }
    & $python @serverArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
