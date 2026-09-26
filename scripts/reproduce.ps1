$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve-python.ps1')
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Resolve-ProjectPython -WorkspaceRoot $root -RequiredModules @('pytest','cv2','numpy')
Push-Location $root
try { & $python -m pytest -q tests/test_sports_play_lab.py; exit $LASTEXITCODE }
finally { Pop-Location }
