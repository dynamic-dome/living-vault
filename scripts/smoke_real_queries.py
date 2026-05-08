"""Smoke test: run a few queries against the real indexed vault."""
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.embeddings import search_semantic, similar
from living_vault.core import graph

DB = Path(r"C:\Users\domes\wiki\.vault-engine.db")

con = db_mod.connect(DB)
try:
    print("--- search_semantic('living vault project') top 5 ---")
    for path, score in search_semantic(con, "living vault project", k=5):
        print(f"  {score:.3f}  {path}")

    print("\n--- search_semantic('cv bewerbung lebenslauf') top 5 ---")
    for path, score in search_semantic(con, "cv bewerbung lebenslauf", k=5):
        print(f"  {score:.3f}  {path}")

    print("\n--- search_semantic('mcp protocol') top 5 ---")
    for path, score in search_semantic(con, "mcp protocol", k=5):
        print(f"  {score:.3f}  {path}")

    # pick the top result of the first query and find similar
    top = search_semantic(con, "living vault project", k=1)
    if top:
        path, _ = top[0]
        print(f"\n--- similar('{path}') top 5 ---")
        for p, s in similar(con, path, k=5):
            print(f"  {s:.3f}  {p}")
        nbs = graph.neighbors(con, path)
        print(f"\n--- neighbors('{path}') ---")
        for n in nbs[:10]:
            print(f"  {n}")
finally:
    con.close()
