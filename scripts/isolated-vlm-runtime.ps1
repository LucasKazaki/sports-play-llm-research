param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("prepare", "start", "status", "stop", "restore")]
    [string]$Action,
    [string]$State = "",
    [string]$Receipt = "",
    [string]$Binary = "",
    [string]$ModelFile = "",
    [string]$MmprojFile = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-soccernet\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing isolated SoccerNet environment: $python"
}
if (-not $State) {
    $State = Join-Path $projectRoot ".agent\isolated-vlm-runtime-state.json"
}

$runtimeArguments = @(
    (Join-Path $projectRoot "prototype\isolated_vlm_runtime.py"),
    $Action,
    "--state", $State
)
if ($Action -eq "start") {
    if (-not $Receipt -or -not $Binary -or -not $ModelFile -or -not $MmprojFile) {
        throw "start requires -Receipt, -Binary, -ModelFile, and -MmprojFile."
    }
    $runtimeArguments += @(
        "--receipt", $Receipt,
        "--binary", $Binary,
        "--model-file", $ModelFile,
        "--mmproj-file", $MmprojFile
    )
} elseif ($Action -eq "status" -and $Receipt) {
    $runtimeArguments += @("--receipt", $Receipt)
}

& $python @runtimeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Isolated VLM runtime action '$Action' failed with exit code $LASTEXITCODE."
}
