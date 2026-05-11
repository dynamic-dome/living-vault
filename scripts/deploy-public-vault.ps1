# Phase-11 — Public-Vault build + (optional) deploy-target copy.
#
# Default: builds out-vault/ via synesthesia-public-build.
# Pass -DeployTarget <path> to additionally copy the build into a
# static-host source directory.
#
# Examples:
#   ./scripts/deploy-public-vault.ps1
#   ./scripts/deploy-public-vault.ps1 -OpenManifest
#   ./scripts/deploy-public-vault.ps1 -DeployTarget 'C:\path\to\host\source'

param(
    # Inner wiki content root — matches the convention used by LIVING_VAULT_ROOT
    # and the allowlist (relpaths are relative to this directory, not $HOME\wiki).
    # Using $HOME\wiki here breaks Phase-13 history.json (git log finds no commits
    # because vault_root/relpath then points one directory above the actual files).
    [string]$Vault     = "$HOME\wiki\wiki",
    [string]$Db        = "$HOME\wiki\.vault-engine.db",
    [string]$Allowlist = "$PSScriptRoot\..\docs\public-allowlist.txt",
    [string]$OutDir    = "$PSScriptRoot\..\out-vault",
    [string]$Variant   = "default",
    [string]$EmbedUrl  = "https://vault.dynamic-dome.com",
    [string]$DeployTarget,
    [switch]$OpenManifest
)

$ErrorActionPreference = "Stop"

# Resolve project root + venv
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$Venv        = Join-Path $ProjectRoot ".venv\Scripts"
$EntryPoint  = Join-Path $Venv "synesthesia-public-build.exe"
$VenvPython  = Join-Path $Venv "python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error ".venv not found at $VenvPython. Run: python -m venv .venv ; .venv\Scripts\pip install -e `".[embeddings,dev]`""
}

if (-not (Test-Path $Db)) {
    Write-Error "Vault DB not found: $Db. Run living-vault index first."
}

# Assemble build args
$buildArgs = @(
    "--vault", $Vault,
    "--db", $Db,
    "--out", $OutDir,
    "--variant", $Variant,
    "--embed-url", $EmbedUrl
)
if (Test-Path $Allowlist) {
    $buildArgs += @("--allowlist", $Allowlist)
} else {
    Write-Host "[deploy-public-vault] no allowlist at $Allowlist (frontmatter-only build)" -ForegroundColor Yellow
}

# Build
Write-Host "[deploy-public-vault] building $OutDir ..." -ForegroundColor Cyan
if (Test-Path $EntryPoint) {
    & $EntryPoint @buildArgs
} else {
    # Entry point not installed: invoke via -m
    Write-Host "[deploy-public-vault] entry point not installed; using python -m" -ForegroundColor Yellow
    & $VenvPython -m "living_vault.apps.synesthesia.render_public_build_main" @buildArgs
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "public-build failed (exit $LASTEXITCODE)"
}

# Manifest summary
$Manifest = Join-Path $OutDir "manifest.json"
if (Test-Path $Manifest) {
    $m = Get-Content $Manifest -Raw | ConvertFrom-Json
    Write-Host ""
    Write-Host "[deploy-public-vault] build OK" -ForegroundColor Green
    Write-Host "  public_total           = $($m.public_total)"
    Write-Host "  via frontmatter        = $($m.public_via_frontmatter)"
    Write-Host "  via allowlist          = $($m.public_via_allowlist)"
    Write-Host "  allowlist_skipped      = $($m.allowlist_skipped.Count)"
    Write-Host "  edges_total            = $($m.edges_total)"
    Write-Host "  build_at               = $($m.build_at)"

    if ($OpenManifest) {
        Write-Host ""
        Get-Content $Manifest -Raw
    }
}

# Optional: copy to static-host source
if ($DeployTarget) {
    if (-not (Test-Path $DeployTarget)) {
        Write-Error "DeployTarget does not exist: $DeployTarget"
    }
    Write-Host ""
    Write-Host "[deploy-public-vault] copying $OutDir -> $DeployTarget ..." -ForegroundColor Cyan
    Copy-Item -Recurse -Force "$OutDir\*" $DeployTarget
    Write-Host "[deploy-public-vault] copy OK" -ForegroundColor Green
    Write-Host "  next: trigger your static-host (see docs/DEPLOY-PUBLIC-VAULT.md)"
}
