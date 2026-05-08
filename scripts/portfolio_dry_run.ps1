$tmp = New-Item -ItemType Directory -Path "$env:TEMP\livv-pf-$(Get-Random)"
$env:LIVING_VAULT_PORTFOLIO_DIR = $tmp.FullName
Write-Output "tmp target: $($tmp.FullName)"
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\portfolio-sync.exe' sync --vault 'C:\Users\domes\wiki\wiki' --db 'C:\Users\domes\wiki\.vault-engine.db' --dry-run
Write-Output "---"
Write-Output "cleanup..."
Remove-Item -Recurse -Force $tmp.FullName -ErrorAction SilentlyContinue
Remove-Item Env:LIVING_VAULT_PORTFOLIO_DIR
