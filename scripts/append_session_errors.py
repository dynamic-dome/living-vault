"""Append session errors + iteration to agent-memory.

Idempotent: re-runs would create dupes, so only run once at session end.
"""
import json
from pathlib import Path

ERRORS_PATH = Path(r"C:\Users\domes\desktop\.agent-memory\iterations\errors.json")
ITER_LOG = Path(r"C:\Users\domes\desktop\.agent-memory\iterations\iteration-log.md")

errors = json.loads(ERRORS_PATH.read_text(encoding="utf-8"))
existing_ids = {e["id"] for e in errors}

new_errors = [
    {
        "id": "2026-05-08-living-vault-row-factory-test-conflict",
        "timestamp": "2026-05-08T19:30:00+02:00",
        "category": "test",
        "severity": "minor",
        "trigger": "Task 5 implementer (Sonnet subagent) entdeckte beim TDD-Lauf einen Konflikt zwischen Plan-Spec und Test-Assertion.",
        "problem": "Plan schrieb 'connect() liefert Connection mit row_factory=sqlite3.Row', aber der Test asserte `con.execute('SELECT 1').fetchone() == (1,)` — sqlite3.Row ist kein Tuple, Vergleich faellt false. Implementer entschied DONE_WITH_CONCERNS und liess row_factory weg um Test gruen zu bekommen, flaggte den Konflikt.",
        "root_cause": "Spec-Bug im Plan: Test-Beispielcode wurde ohne Beruecksichtigung der spaeteren row_factory=Row-Konvention geschrieben (die in den meisten Folge-Tasks per `r['path']`-Subscript gebraucht wird). Spec-Self-Review im Plan-Skill hat die Inkonsistenz nicht gefunden.",
        "solution": "Test korrigiert auf `tuple(row) == (1,)`, row_factory=Row in db.py wieder hinzugefuegt. Folge-Task-Code (indexer, decay, privacy, layout, persona, store) konnte dadurch wie geplant `row['col']`-Zugriff nutzen — kein Refactor noetig.",
        "attempts": 1,
        "failed_approaches": [],
        "files_changed": [
            "C:/Users/domes/desktop/Claude-Projekte/living-vault/living_vault/core/db.py",
            "C:/Users/domes/desktop/Claude-Projekte/living-vault/tests/test_db.py"
        ],
        "tags": ["living-vault", "tdd", "spec-bug", "sqlite3-row", "subagent-flag"],
        "reusable_pattern": "Implementer-Subagents sollen DONE_WITH_CONCERNS melden statt still falsch zu implementieren — der Pattern hat hier funktioniert. Self-Review-Checkliste im writing-plans-Skill sollte explizit auf Type-/API-Konsistenz zwischen Test-Code und Impl-Code achten."
    },
    {
        "id": "2026-05-08-living-vault-three-importmap-missing",
        "timestamp": "2026-05-08T22:10:00+02:00",
        "category": "integration",
        "severity": "major",
        "trigger": "User oeffnete vault-3d.html im Browser, sah komplett schwarz statt 3D-Wolke. F12-Console: `Uncaught TypeError: The specifier 'three' was a bare specifier, but was not remapped to anything`.",
        "problem": "Three.js OrbitControls.js (von unpkg.com geladen) macht intern `import { ... } from 'three'`. Ohne Browser-importmap ist 'three' kein gueltiger Specifier — Browser bricht das Modul-Loading ab. Banner war sichtbar (HTML lud), Three.js core lief, aber OrbitControls scheiterte und damit kein Setup der Szene.",
        "root_cause": "Plan-Template uebernahm gaengiges Three.js-Pattern aus aelteren Tutorials, ohne den dazugehoerigen importmap-Block. Three.js-Module-Distribution braucht den seit ~v0.150 zwingend.",
        "solution": "Importmap im HTML-template ergaenzt: `{ \"imports\": { \"three\": \"https://unpkg.com/three@0.160.0/build/three.module.js\", \"three/addons/\": \"https://unpkg.com/three@0.160.0/examples/jsm/\" } }` und Imports im Modul-Script auf 'three' / 'three/addons/...' umgestellt. Re-render, Hard-Reload, fix bestaetigt.",
        "attempts": 1,
        "failed_approaches": [],
        "files_changed": [
            "C:/Users/domes/desktop/Claude-Projekte/living-vault/living_vault/apps/synesthesia/templates/vault-3d.html.j2"
        ],
        "tags": ["living-vault", "synesthesia", "three.js", "importmap", "browser-modules", "missing-config"],
        "reusable_pattern": "Bei JS-Modul-Imports mit bare-specifier-Pattern (`from 'three'`, `from 'react'`) ist immer eine importmap noetig oder ein Build-Step (Vite/esbuild). CDN-pure HTML braucht expliziten importmap-Block."
    },
    {
        "id": "2026-05-08-living-vault-seance-schema-not-initialized",
        "timestamp": "2026-05-08T23:45:00+02:00",
        "category": "integration",
        "severity": "major",
        "trigger": "Seance UI lief auf 127.0.0.1:7777, summon klappte nicht: 500 Internal Server Error. Server-Log: `sqlite3.OperationalError: no such table: seance_sessions`.",
        "problem": "Die echte Vault-DB (~/wiki/.vault-engine.db) wurde in Etappe 4 (Bench, Phase-1 Indexing) angelegt, BEVOR Task 29 die seance-Tabellen ins SCHEMA aufnahm. Die Tabellen wurden also nie erstellt. Seance-App rief direkt `store.new_session()` ohne vorher `db.initialize()` zu callen — der Initial-Indexing-Lauf wuerde initialize aufrufen, aber bei einem reinen Seance-Server-Start nicht.",
        "root_cause": "Lifecycle-Luecke: db.initialize ist idempotent und genau fuer solche Schema-Migrations gedacht, aber kein App-Component rief es bei Server-Start auf. Plan hatte das implizit — die Annahme war 'der erste living-vault index Lauf macht das'.",
        "solution": "FastAPI `@app.on_event('startup')` Hook hinzugefuegt, der `db_mod.initialize(_db_path())` ausfuehrt. Tests laufen weiterhin (TestClient triggert startup-events). DeprecationWarning fuer on_event ignoriert (lifespan-API-Migration ist Phase-2-Polish).",
        "attempts": 1,
        "failed_approaches": [],
        "files_changed": [
            "C:/Users/domes/desktop/Claude-Projekte/living-vault/living_vault/apps/seance_ui/app.py"
        ],
        "tags": ["living-vault", "seance", "fastapi", "schema-migration", "lifecycle", "startup-event"],
        "reusable_pattern": "Apps die schema-erweiternde Tabellen einfuehren brauchen einen Startup-Hook, der das idempotente `initialize()` der zentralen Schema-Definition aufruft. Sonst greift die Migration nur dann, wenn zufaellig der DB-init-Pfad ueber das alte Tool laeuft."
    }
]

added = 0
for ne in new_errors:
    if ne["id"] in existing_ids:
        print(f"  skip duplicate: {ne['id']}")
        continue
    errors.append(ne)
    added += 1

ERRORS_PATH.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"appended {added} new errors, total now {len(errors)}")
