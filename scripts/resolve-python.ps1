function Resolve-ProjectPython {
  param([string]$WorkspaceRoot = '', [string[]]$RequiredModules = @())

  $candidates = @()
  if ($WorkspaceRoot) {
    $candidates += @(
      (Join-Path $WorkspaceRoot '.venv-soccernet\Scripts\python.exe'),
      (Join-Path $WorkspaceRoot '.venv\Scripts\python.exe')
    )
  }

  # Packaged processes may not inherit the interactive PATH. Check ordinary
  # per-user CPython installs before the PATH fallback.
  $localRoots = @(
    $env:LOCALAPPDATA,
    $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE 'AppData\Local' })
  ) | Where-Object { $_ } | Select-Object -Unique
  foreach ($localRoot in $localRoots) {
    $pythonRoot = Join-Path $localRoot 'Programs\Python'
    if (-not (Test-Path -LiteralPath $pythonRoot)) { continue }
    $candidates += Get-ChildItem -LiteralPath $pythonRoot -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match '^Python[0-9]+(?:[._-][0-9]+)*$' } |
      Sort-Object Name -Descending |
      ForEach-Object { Join-Path $_.FullName 'python.exe' }
  }
  $command = Get-Command python -ErrorAction SilentlyContinue
  if ($command -and $command.Source -notmatch '[\\/]Microsoft[\\/]WindowsApps[\\/]') {
    $candidates += $command.Source
  }

  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $probe = if ($RequiredModules.Count) { 'import ' + ($RequiredModules -join ', ') } else { 'import sys' }
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $candidate -c $probe *> $null
      $probeExitCode = $LASTEXITCODE
    } catch {
      $probeExitCode = 1
    } finally {
      $ErrorActionPreference = $priorPreference
    }
    if ($probeExitCode -eq 0) { return $candidate }
  }
  throw "No Python interpreter satisfies required modules: $($RequiredModules -join ', '). Run scripts/bootstrap.ps1 from the repository root."
}
