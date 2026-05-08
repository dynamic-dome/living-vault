$env:LIVING_VAULT_ROOT = 'C:\Users\domes\wiki\wiki'
$env:LIVING_VAULT_DB   = 'C:\Users\domes\wiki\.vault-engine.db'
$base = 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\synesthesia.exe'

foreach ($variant in 'galaxy','city','network') {
  $out = "$env:USERPROFILE\desktop\vault-3d-$variant.html"
  & $base --db $env:LIVING_VAULT_DB --output $out --variant $variant
  Write-Output "size: $((Get-Item $out).Length) bytes"
}
