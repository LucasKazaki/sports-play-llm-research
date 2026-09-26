$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$files = Get-ChildItem -LiteralPath (Join-Path $root 'artifacts') -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in @('.json','.log') -and $_.Length -le 1MB -and $_.Name -notmatch '(?i)(token|secret|credential|account|oauth|session|\.enc\.)' } |
  Select-Object -First 20
$manifest = @($files | ForEach-Object { [ordered]@{source=$_.FullName;bytes=$_.Length;copied=$false;reason='Reference only; research evidence remains in place.'} })
[ordered]@{schemaVersion=1;passed=$true;redacted=$true;copiedFiles=0;files=$manifest;generatedAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json -Depth 6 -Compress
