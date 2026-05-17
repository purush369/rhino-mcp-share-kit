param(
    [string]$MarketplaceName = "rhino-local"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$sourceRoot = Join-Path $packageRoot "claude-marketplace\\rhino-local"
$claudeHome = Join-Path $env:USERPROFILE ".claude"
$targetRoot = Join-Path $claudeHome ("local-marketplaces\\" + $MarketplaceName)
$settingsPath = Join-Path $claudeHome "settings.json"

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    throw "Source Claude marketplace folder not found: $sourceRoot"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetRoot) | Out-Null

if (Test-Path -LiteralPath $targetRoot) {
    $backup = "{0}.backup-{1}" -f $targetRoot, (Get-Date -Format "yyyyMMdd-HHmmss")
    Move-Item -LiteralPath $targetRoot -Destination $backup
    Write-Host "Backed up existing Claude marketplace to: $backup"
}

Copy-Item -LiteralPath $sourceRoot -Destination $targetRoot -Recurse -Force
Write-Host "Installed Claude marketplace to: $targetRoot"

if (-not (Test-Path -LiteralPath $settingsPath)) {
    '{}' | Set-Content -LiteralPath $settingsPath -Encoding UTF8
}

$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json

if (-not $settings.PSObject.Properties['enabledPlugins']) {
    $settings | Add-Member -MemberType NoteProperty -Name enabledPlugins -Value ([pscustomobject]@{})
}
if (-not $settings.PSObject.Properties['extraKnownMarketplaces']) {
    $settings | Add-Member -MemberType NoteProperty -Name extraKnownMarketplaces -Value ([pscustomobject]@{})
}

$pluginKey = "rhino@rhino-local"
$settings.enabledPlugins | Add-Member -MemberType NoteProperty -Name $pluginKey -Value $true -Force
$settings.extraKnownMarketplaces | Add-Member -MemberType NoteProperty -Name $MarketplaceName -Value ([pscustomobject]@{
    source = [pscustomobject]@{
        source = "directory"
        path = $targetRoot
    }
}) -Force

$settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
Write-Host "Updated Claude settings: $settingsPath"

$claudeExe = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeExe) {
    Write-Host "Adding Rhino MCP server to Claude..."
    try {
        & claude mcp add --transport http rhino http://localhost:4862 | Out-Host
    } catch {
        Write-Warning "Could not automatically add the Claude MCP server. You can run this manually:"
        Write-Host "claude mcp add --transport http rhino http://localhost:4862"
    }
} else {
    Write-Host "Claude CLI was not found on PATH."
    Write-Host "Run this manually if needed:"
    Write-Host "claude mcp add --transport http rhino http://localhost:4862"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Restart Claude."
Write-Host "2. Open Rhino."
Write-Host "3. Run RhinoMCP in Rhino."
Write-Host "4. Use /rhino-mcp or ask Claude to create geometry in Rhino."
