param(
  [int]$Port = 8793,
  [string]$ModelDir = '',
  [switch]$NoModel
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$python = Resolve-ProjectPython -WorkspaceRoot $repoRoot -RequiredModules @('chess')
$arguments = @((Join-Path $repoRoot 'prototype/chess_tutor_v1/server.py'), '--port', "$Port")
if (-not $NoModel) {
  # Explicit experimental candidate selected on the historical development set.
  # This never auto-promotes a new checkpoint or imports remote model code.
  if (-not $ModelDir) { $ModelDir = Join-Path $repoRoot 'data/private/chess-classifier-v3/checkpoints/step-512' }
  if (-not (Test-Path -LiteralPath (Join-Path $ModelDir 'model.safetensors'))) {
    throw "Local model weights not found. Supply -ModelDir or use -NoModel."
  }
  $arguments += @('--model-dir', $ModelDir)
}
Write-Host "Starting the local chess study candidate at http://127.0.0.1:$Port/ (Ctrl+C stops it)."
& $python @arguments
exit $LASTEXITCODE
