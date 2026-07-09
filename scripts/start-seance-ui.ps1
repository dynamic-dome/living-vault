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

function Get-IndexedPageCount {
    if (-not (Test-Path -LiteralPath $VaultDb)) {
        return 0
    }

    $code = @"
import sqlite3
from pathlib import Path

db = Path(r"$VaultDb")
try:
    con = sqlite3.connect(db)
    try:
        has_pages = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pages'"
        ).fetchone()
        if not has_pages:
            print(0)
        else:
            print(con.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
    finally:
        con.close()
except Exception:
    print(0)
"@

    $output = & (Join-Path $VenvScripts "python.exe") -c $code
    $count = 0
    if ([int]::TryParse(($output | Select-Object -Last 1), [ref] $count)) {
        return $count
    }
    return 0
}

Ensure-Command -Path $SeanceUi -Label "seance-ui"
Ensure-Command -Path $LivingVault -Label "living-vault"
Ensure-Command -Path $VaultRoot -Label "Vault root"

$env:LIVING_VAULT_ROOT = $VaultRoot
$env:LIVING_VAULT_DB = $VaultDb

function Test-VaultNewerThanDb {
    if (-not (Test-Path -LiteralPath $VaultDb)) {
        return $true
    }
    $dbTime = (Get-Item -LiteralPath $VaultDb).LastWriteTime
    $newest = Get-ChildItem -LiteralPath $VaultRoot -Recurse -Filter *.md -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $newest) {
        return $false
    }
    return ($newest.LastWriteTime -gt $dbTime)
}

# Re-index (incremental, WITH embeddings) when the DB is empty or the vault
# changed since the last index. The server must not be running concurrently:
# journal_mode=delete means a parallel index would risk "database is locked".
if (((Get-IndexedPageCount) -eq 0) -or (Test-VaultNewerThanDb)) {
    Write-Host "Indexing vault for Seance UI (with embeddings)..."
    & $LivingVault index --vault $VaultRoot --db $VaultDb
}

if (Test-SeanceRunning) {
    Start-Process $Url
    return
}

Write-Host "Starting Seance UI at $Url"
Write-Host "Close this window to stop the server."
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process '$Url'"
)
& $SeanceUi
