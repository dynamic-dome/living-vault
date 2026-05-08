$env:LIVING_VAULT_ROOT = 'C:\Users\domes\wiki\wiki'
$env:LIVING_VAULT_DB   = 'C:\Users\domes\wiki\.vault-engine.db'
# WICHTIG: kein LIVING_VAULT_FAKE_LLM — echte Anthropic-API wird genutzt
& 'C:\Users\domes\desktop\Claude-Projekte\living-vault\.venv\Scripts\seance-ui.exe'
