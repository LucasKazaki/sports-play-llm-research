[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venv = Join-Path $root '.venv-soccernet'
$python = Join-Path $venv 'Scripts\python.exe'
$requirements = Join-Path $root 'requirements-windows-py311.lock.txt'

if (-not (Test-Path -LiteralPath $python)) {
  $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
  if ($launcher) {
    & $launcher.Source -3.11 -m venv $venv
  } else {
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $systemPython) { throw 'Install Python 3.11, then run this script again.' }
    $version = & $systemPython.Source -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3.11') {
      throw 'Install Python 3.11, then run this script again.'
    }
    & $systemPython.Source -m venv $venv
  }
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
}

if (-not (Test-Path -LiteralPath $requirements)) { throw "Dependency lock is missing: $requirements" }
& $python -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Could not install the pinned Python dependencies.' }
Write-Output "Project environment ready: $python"
