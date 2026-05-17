param(
    [string]$MarketplaceName = "rhino-local"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$sourceRoot = Join-Path $packageRoot "codex-marketplace\\rhino-local"
$codexHome = Join-Path $env:USERPROFILE ".codex"
$targetRoot = Join-Path $codexHome ("local-marketplaces\\" + $MarketplaceName)
$configPath = Join-Path $codexHome "config.toml"

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    throw "Source marketplace folder not found: $sourceRoot"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetRoot) | Out-Null

if (Test-Path -LiteralPath $targetRoot) {
    $backup = "{0}.backup-{1}" -f $targetRoot, (Get-Date -Format "yyyyMMdd-HHmmss")
    Move-Item -LiteralPath $targetRoot -Destination $backup
    Write-Host "Backed up existing marketplace to: $backup"
}

Copy-Item -LiteralPath $sourceRoot -Destination $targetRoot -Recurse -Force
Write-Host "Installed marketplace to: $targetRoot"

if (-not (Test-Path -LiteralPath $configPath)) {
    New-Item -ItemType File -Path $configPath | Out-Null
}

$configText = Get-Content -LiteralPath $configPath -Raw
$marketplaceBlockHeader = "[marketplaces.$MarketplaceName]"
$pluginBlockHeader = "[plugins.`"rhino@$MarketplaceName`"]"

if ($configText -notmatch [regex]::Escape($marketplaceBlockHeader)) {
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $verbatimPath = "\\?\$targetRoot"
    $appendBlock = @"

[marketplaces.$MarketplaceName]
last_updated = "$timestamp"
source_type = "local"
source = '$verbatimPath'

[plugins."rhino@$MarketplaceName"]
enabled = true
"@
    Add-Content -LiteralPath $configPath -Value $appendBlock
    Write-Host "Updated Codex config: $configPath"
} else {
    Write-Host "Codex config already contains $marketplaceBlockHeader"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Restart Codex."
Write-Host "2. Open Rhino."
Write-Host "3. Run RhinoMCP in Rhino."
Write-Host "4. Ask Codex to create or inspect Rhino geometry."
