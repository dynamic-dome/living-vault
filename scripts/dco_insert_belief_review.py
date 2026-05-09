import sqlite3, time
c = sqlite3.connect(r"C:\Users\domes\dynamic_central_orchestrator\data\todos.db")
now = time.time()
text = ("[FAELLIG 2026-11-09] Belief-Review LLM-Sprung-These wiederlesen. "
        "Source: wiki/synthesis/2026-05-09-llm-sprung-und-positionelles-bauen.md "
        "+ wiki/sources/2026-05-09-llm-sprung-reflexionsgespraech.md "
        "+ wiki/todos/2026-11-09-belief-review-llm-sprung.md. "
        "Pruefen: F1 Adoption (3 externe Nutzer), F2 Begriffs-Konvergenz, F3 Selbst-Test. "
        "Entscheiden: bestaetigt | revidiert | belief-graveyard.")
cur = c.execute(
    "INSERT INTO todos(chat_id, text, done, tag, created_at, updated_at, last_touched_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)",
    (8630776278, text, 0, "sonst", now, now, now),
)
c.commit()
print(f"inserted DCO todo_id={cur.lastrowid}")
c.close()
