$env:LIVING_VAULT_ROOT = 'C:\Users\domes\wiki\wiki'
$env:LIVING_VAULT_DB   = 'C:\Users\domes\wiki\.vault-engine.db'
$out = "$env:USERPROFILE\desktop\vault-3d.html"
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\synesthesia.exe' --db $env:LIVING_VAULT_DB --output $out
$size = (Get-Item $out).Length
Write-Output "wrote: $out"
Write-Output "size: $size bytes"
