$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvScripts = Join-Path $ProjectRoot ".venv\Scripts"
$SeanceUi = Join-Path $VenvScripts "seance-ui.exe"
$LivingVault = Join-Path $VenvScripts "living-vault.exe"
$VaultRoot = "C:\Users\domes\wiki\wiki"
$VaultDb = "C:\Users\domes\wiki\.vault-engine.db"
$Url = "http://127.0.0.1:7777"

function Test-SeanceRunning {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    }
    catch {
        return $false
    }
}

function Ensure-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,
        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

Ensure-Command -Path $SeanceUi -Label "seance-ui"
Ensure-Command -Path $LivingVault -Label "living-vault"
Ensure-Command -Path $VaultRoot -Label "Vault root"

$env:LIVING_VAULT_ROOT = $VaultRoot
$env:LIVING_VAULT_DB = $VaultDb

if (Test-SeanceRunning) {
    Start-Process $Url
    return
}

if (-not (Test-Path -LiteralPath $VaultDb)) {
    Write-Host "Indexing vault for Seance UI..."
    & $LivingVault index --vault $VaultRoot --db $VaultDb --no-embed
}

Write-Host "Starting Seance UI at $Url"
Write-Host "Close this window to stop the server."
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process '$Url'"
)
& $SeanceUi
