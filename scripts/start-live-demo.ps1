$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$demoRoot = Join-Path $projectRoot "data\private\demo-soccernet-valid-qwen35-comparison-v1"
$python = Join-Path $projectRoot ".venv-soccernet\Scripts\python.exe"
$url = "http://127.0.0.1:8765/"

if (-not (Test-Path -LiteralPath (Join-Path $demoRoot "index.html") -PathType Leaf)) {
    throw "The verified live-demo build is missing. Expected: $demoRoot"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "The project Python runtime is missing. Expected: $python"
}

function Test-ExpectedDemo {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200 -and $response.Content.Contains("qwen/qwen3.5-9b")
    }
    catch {
        return $false
    }
}

if (-not (Test-ExpectedDemo)) {
    $portOwner = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if ($null -ne $portOwner) {
        throw "Port 8765 is already serving a different page. Close that local server and run this launcher again."
    }
    Start-Process -FilePath $python `
        -ArgumentList @("-m", "http.server", "8765", "--bind", "127.0.0.1") `
        -WorkingDirectory $demoRoot `
        -WindowStyle Hidden
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        Start-Sleep -Milliseconds 250
        if (Test-ExpectedDemo) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        throw "The local demo server did not become ready at $url"
    }
}

Start-Process $url
Write-Host "PlayGround live demo is ready at $url"
