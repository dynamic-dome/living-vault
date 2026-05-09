import sqlite3
c = sqlite3.connect(r"C:\Users\domes\dynamic_central_orchestrator\data\todos.db")
print("--- tables ---")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(r[0])
print("--- todos schema ---")
for r in c.execute("PRAGMA table_info(todos)"):
    print(r)
print("--- last 3 rows ---")
for r in c.execute("SELECT * FROM todos ORDER BY id DESC LIMIT 3"):
    print(r)
c.close()
