"""Append new learnings from this session to learnings.json."""
import json
from pathlib import Path

LEARN = Path(r"C:\Users\domes\desktop\.agent-memory\learnings.json")
data = json.loads(LEARN.read_text(encoding="utf-8"))

# determine next id
ids = [x.get("id", "") for x in data]
nums = [int(i[1:]) for i in ids if i.startswith("L") and i[1:].isdigit()]
next_n = (max(nums) + 1) if nums else 1

new = [
    {
        "id": f"L{next_n:04d}",
        "date": "2026-05-09",
        "category": "methodology",
        "lesson": "Etappierung von 37-Task-Plaenen in 7 Etappen mit User-Status-Bericht zwischen jeder Etappe verhindert Token-Erschoepfung des Hauptmodells und gibt User echte Pruef-Punkte ohne den Build-Flow zu unterbrechen.",
        "context": "living-vault Phase 1, ~25 Subagent-Dispatches gesamt. Ohne Etappierung waere der Hauptmodell-Context bei Task ~25-30 erschoepft gewesen. Mit Etappierung 7 saubere Statusberichte + User-Akzeptanz vor naechster Etappe.",
        "applicability": "alle subagent-driven-development-Plans mit >20 Tasks. Etappen-Schnitt entlang natuerlicher Komponenten-Grenzen, nicht nach Anzahl Tasks.",
        "tags": ["subagent-driven-development", "etappierung", "token-management", "phase-gate"],
    },
    {
        "id": f"L{next_n+1:04d}",
        "date": "2026-05-09",
        "category": "tdd",
        "lesson": "Implementer-Subagents mit DONE_WITH_CONCERNS-Disziplin fangen echte Spec-Bugs ab, statt sie zu ueberdecken. In living-vault Task 5 hat das einen Plan-Bug (row_factory vs. Test-Assertion) sichtbar gemacht, der sonst alle Folge-Tasks behindert haette.",
        "context": "TDD-Plan hatte Test-Code geschrieben, der mit der spaeter-genutzten Konvention `row_factory=sqlite3.Row` inkompatibel war. Implementer hat Implementation gegen Test gewinnen lassen, aber den Konflikt geflagged.",
        "applicability": "writing-plans-Skill: Self-Review-Checkliste sollte Type-/API-Konsistenz zwischen Test-Code und Impl-Code explizit pruefen.",
        "tags": ["tdd", "subagent", "spec-bug", "self-review", "writing-plans"],
    },
    {
        "id": f"L{next_n+2:04d}",
        "date": "2026-05-09",
        "category": "lifecycle",
        "lesson": "Apps die schema-erweiternde Tabellen einfuehren, brauchen einen Startup-Hook der das idempotente initialize() der zentralen Schema-Definition aufruft. Sonst greift die Migration nur dann, wenn zufaellig der DB-init-Pfad ueber das alte Tool laeuft.",
        "context": "living-vault Seance: seance_sessions/messages-Tabellen wurden NACH Bench-Indexing-Lauf hinzugefuegt. Echte DB hatte sie nie - 500 beim ersten summon-Call. Fix: FastAPI on_event(startup) ruft db.initialize().",
        "applicability": "alle FastAPI-/Flask-/etc.-Apps mit eigener Persistenz. Idempotenter initialize-Hook gehoert in den Startup-Lifecycle, nicht implizit ueber den ersten User-Call.",
        "tags": ["fastapi", "lifecycle", "schema-migration", "startup-event", "idempotence"],
    },
    {
        "id": f"L{next_n+3:04d}",
        "date": "2026-05-09",
        "category": "browser",
        "lesson": "Three.js seit ~v0.150 braucht zwingend einen importmap-Block im HTML, damit Submodule wie OrbitControls ihren internen `import 'three'` aufloesen koennen. Aeltere Tutorials lassen das oft weg - der Banner laedt, JS startet, scheitert dann an Modul-Imports und das Canvas bleibt leer.",
        "context": "living-vault synesthesia: Browser zeigte komplett schwarz. F12-Console: `bare specifier 'three' was not remapped`. Fix: importmap-Block ergaenzt mit `three` und `three/addons/`-Mappings.",
        "applicability": "alle JS-Modul-Imports mit bare-specifier-Pattern (from 'react', from 'three', etc.) in CDN-pure HTML. Entweder importmap oder Build-Step.",
        "tags": ["three.js", "importmap", "browser-modules", "frontend", "es-modules"],
    },
    {
        "id": f"L{next_n+4:04d}",
        "date": "2026-05-09",
        "category": "epistemic",
        "lesson": "Beliefs mit Wiedervorlage-Datum + eingebauten Falsifikationskriterien + Cross-Check durch zweite Stimme (Codex) sind robuster als Beliefs die nur einmal aufgeschrieben werden. Beide unabhaengigen Reviews haben unabhaengig zum gleichen Schluss gefuehrt - das ist Teil des Belegs, nicht nur Meinung.",
        "context": "Belief-Capture nach Reflexionsgespraech mit Wiki-Page ueber LLM-Sprung. Codex-Cross-Check angefordert. Wiki-Synthesis enthaelt 3 Gegenhypothesen (Echo-Effekt, Hype-Verzerrung, Builder-Bias) + 3 Falsifikationskriterien (Adoption, Begriffs-Konvergenz, Selbst-Test) + Wiedervorlage 2026-11-09 in DCO #7684.",
        "applicability": "wann immer ein praegender Gedanke auftaucht und der Builder versucht ist, ihn zur Identitaet zu machen. Datierter Belief mit Selbst-Falsifikations-Mechanismus statt sofortigem Pivot. Auch bei normalen Entscheidungen anwendbar.",
        "tags": ["belief-capture", "falsifizierbarkeit", "cross-check", "codex-routine", "epistemics"],
    },
]

added = 0
for n in new:
    if n["id"] in {x.get("id") for x in data}:
        continue
    data.append(n)
    added += 1

LEARN.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"appended {added} learnings, total {len(data)}")
