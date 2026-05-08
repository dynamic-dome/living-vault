# Running vault-engine-mcp with Claude Code

## One-time setup

1. Install the package editable:

       cd C:\Users\domes\desktop\Claude-Projekte\living-vault
       .venv\Scripts\Activate.ps1
       pip install -e ".[embeddings,dev]"

2. Build the initial index (one-time, ~5–10 min for 953 pages):

       $env:LIVING_VAULT_ROOT = "C:\Users\domes\wiki\wiki"
       $env:LIVING_VAULT_DB   = "C:\Users\domes\wiki\.vault-engine.db"
       living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB

## Configure Claude Code

Edit `~/.claude/settings.json` and add an MCP server entry:

```json
{
  "mcpServers": {
    "vault-engine": {
      "command": "C:\\Users\\domes\\desktop\\Claude-Projekte\\living-vault\\.venv\\Scripts\\python.exe",
      "args": ["-m", "living_vault.mcp_servers.vault_engine.server"],
      "env": {
        "LIVING_VAULT_ROOT": "C:\\Users\\domes\\wiki\\wiki",
        "LIVING_VAULT_DB":   "C:\\Users\\domes\\wiki\\.vault-engine.db",
        "PYTHONIOENCODING":  "utf-8"
      }
    }
  }
}
```

## Verify

In a fresh Claude Code session:

> "Use vault-engine.public_pages to list public wiki pages."

You should see a non-empty list (or empty if no `public: true` flag set yet).

## Refresh after vault edits

The server does not yet auto-watch the vault. After substantial editing, run:

       living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB

(Phase 2 will add a file-watcher.)
