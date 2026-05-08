$env:LIVING_VAULT_ROOT = 'C:\Users\domes\wiki\wiki'
$env:LIVING_VAULT_DB   = 'C:\Users\domes\wiki\.vault-engine.db'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\living-vault.exe' index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB
$sw.Stop()
Write-Output "--- ELAPSED $($sw.Elapsed.TotalSeconds) seconds ---"
