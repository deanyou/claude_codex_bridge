param(
  [Parameter(Position = 0)]
  [ValidateSet("install", "uninstall", "help")]
  [string]$Command = "help",
  [string]$InstallPrefix = "$env:LOCALAPPDATA\codex-dual",
  [string]$SourceArchive = "",
  [string]$ExpectedSha256 = "",
  [string]$TmuxLayout = "",
  [switch]$Yes
)

$ErrorActionPreference = "Stop"
$installer = Join-Path $PSScriptRoot "platforms\windows\installer\install.ps1"
if (-not (Test-Path -LiteralPath $installer)) {
  throw "Windows installer implementation not found: $installer"
}

if (-not [string]::IsNullOrWhiteSpace($TmuxLayout)) {
  # Windows native install uses Herdr for the tmux-equivalent backend.
  # tmux layout shorthand is intentionally not applicable here; we surface
  # the notice so callers don't silently assume it took effect.
  Write-Host "INFO: --tmux-layout '$TmuxLayout' ignored on Windows native install (Herdr layout path)" -ForegroundColor Yellow
}

& $installer -Command $Command -InstallPrefix $InstallPrefix -SourceArchive $SourceArchive -ExpectedSha256 $ExpectedSha256 -Yes:$Yes
exit $LASTEXITCODE
