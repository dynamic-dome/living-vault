# Test: tempo eine Page als public:true taggen (in der DB direkt, NICHT im Wiki),
# dann dry-run laufen lassen, sehen ob sie auftaucht. DB-State wird danach
# zurückgesetzt damit kein Drift im echten Wiki entsteht.

$tmp = New-Item -ItemType Directory -Path "$env:TEMP\livv-pf-$(Get-Random)"
$env:LIVING_VAULT_PORTFOLIO_DIR = $tmp.FullName

# eine Page als public markieren (nur in DB, nicht im Wiki-File)
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\python.exe' -c "import sqlite3; c=sqlite3.connect(r'C:\Users\domes\wiki\.vault-engine.db'); c.execute(\""UPDATE pages SET is_public=1 WHERE path='overview.md'\""); c.commit(); c.close(); print('overview.md temporarily marked public')"

Write-Output "---"
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\portfolio-sync.exe' sync --vault 'C:\Users\domes\wiki\wiki' --db 'C:\Users\domes\wiki\.vault-engine.db' --dry-run
Write-Output "---"

# state zurücksetzen
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\python.exe' -c "import sqlite3; c=sqlite3.connect(r'C:\Users\domes\wiki\.vault-engine.db'); c.execute(\""UPDATE pages SET is_public=0 WHERE path='overview.md'\""); c.commit(); c.close(); print('overview.md back to private')"

Remove-Item -Recurse -Force $tmp.FullName -ErrorAction SilentlyContinue
Remove-Item Env:LIVING_VAULT_PORTFOLIO_DIR
