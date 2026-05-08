"""Smoke test: server module imports and main() is callable.

We do NOT start the transport in tests (would block). The deeper integration
test against a real MCP client lives outside this test suite.
"""
import importlib


def test_server_module_imports():
    m = importlib.import_module("living_vault.mcp_servers.vault_engine.server")
    assert hasattr(m, "main")
    assert hasattr(m, "mcp")
