param(
    [switch]$Prepare,
    [string]$Output = "",
    [string]$Model = "google/gemma-4-e4b",
    [string]$Endpoint = "http://127.0.0.1:1234/v1",
    [int]$ContextLength = 4096,
    [int]$Parallel = 1,
    [int]$TtlSeconds = 3600
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-soccernet\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing isolated SoccerNet environment: $python"
}
if ($Output -and -not $Prepare) {
    throw "Output requires -Prepare because read-only inspection cannot attest load settings."
}
if ($Prepare -or $Output) {
    throw "Shared Bionic preparation is disabled because external auto-load can invalidate it. Use scripts\isolated-vlm-runtime.ps1."
}

$runtimeArguments = @(
    (Join-Path $projectRoot "prototype\prepare_local_vlm_runtime.py"),
    "--model", $Model,
    "--endpoint", $Endpoint,
    "--context-length", $ContextLength,
    "--parallel", $Parallel,
    "--gpu", "max",
    "--ttl", $TtlSeconds
)
if ($Prepare) {
    $runtimeArguments += "--prepare"
}
if ($Output) {
    $runtimeArguments += @("--output", $Output)
}

& $python @runtimeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Local VLM runtime preflight failed with exit code $LASTEXITCODE."
}
