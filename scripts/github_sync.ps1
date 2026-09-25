[CmdletBinding()]
param(
    [switch]$Commit,
    [switch]$Push,
    [switch]$InitialImport,
    [string]$Message = "Sync verified Sports Play LLM Research state",
    [string]$ExpectedOrigin = "https://github.com/LucasKazaki/sports-play-llm-research.git"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($Push -and -not $Commit) { throw "-Push requires -Commit so every pushed state has a reviewed local commit." }
if ($InitialImport -and -not $Commit) { throw "-InitialImport requires -Commit so the one-time exception is auditable." }
if ((git -C $root rev-parse --is-inside-work-tree) -ne "true") { throw "The selected directory is not a Git repository." }
$origin = (git -C $root remote get-url origin 2>$null).Trim()
if ($origin -ne $ExpectedOrigin) { throw "origin must exactly match the approved private repository before sync." }

$python = Join-Path $root ".venv-soccernet\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
$auditText = & $python (Join-Path $PSScriptRoot "github_sync_audit.py") --root $root
if ($LASTEXITCODE -ne 0) { throw "GitHub mirror audit failed; nothing was staged." }
$audit = $auditText | ConvertFrom-Json
$eligible = @($audit.eligiblePaths | ForEach-Object { [string]$_ })
if ($eligible.Count -eq 0) { throw "The GitHub mirror audit returned no eligible files." }

$stagedBefore = @((git -C $root diff --cached --name-only) | Where-Object { $_ })
$unexpected = @($stagedBefore | Where-Object { $_ -notin $eligible })
if ($unexpected.Count -gt 0) { throw "Existing staged paths are outside the approved mirror list: $($unexpected -join ', ')" }

$temporaryList = [System.IO.Path]::GetTempFileName()
try {
    $nul = [char]0
    [System.IO.File]::WriteAllText($temporaryList, (($eligible -join $nul) + $nul), [System.Text.UTF8Encoding]::new($false))
    & git -C $root add --pathspec-from-file=$temporaryList --pathspec-file-nul
    if ($LASTEXITCODE -ne 0) { throw "Git add failed." }
    $whitespaceFindings = @(& git -C $root diff --cached --check 2>&1)
    $whitespaceExit = $LASTEXITCODE
    if ($whitespaceExit -ne 0) {
        if (-not $InitialImport) {
            $whitespaceFindings | Write-Output
            throw "Staged source failed Git's whitespace check."
        }
        & git -C $root rev-parse --verify --quiet HEAD *> $null
        if ($LASTEXITCODE -eq 0) { throw "-InitialImport is allowed only before the repository's first commit." }
        if ($whitespaceFindings.Count -eq 0) { throw "Git whitespace check failed without retained findings." }
        Write-Warning "Initial import retains $($whitespaceFindings.Count) pre-existing Git whitespace findings; normal sync remains strict after this first commit."
    }
    if (-not $Commit) {
        Write-Output "Audit and staging completed. Re-run with -Commit after reviewing the staged diff."
        exit 0
    }
    & git -C $root diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Output "No eligible changes are pending."
        exit 0
    }
    & git -C $root commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Git commit failed." }
    if ($Push) {
        & git -C $root push --porcelain origin HEAD:main
        if ($LASTEXITCODE -ne 0) { throw "GitHub push failed." }
    }
} finally {
    Remove-Item -LiteralPath $temporaryList -Force -ErrorAction SilentlyContinue
}
