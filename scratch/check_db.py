import sqlite3
conn = sqlite3.connect('app_data/courses_offline.db')
c = conn.cursor()
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
for t in tables:
    t_name = t[0]
    count = c.execute(f"SELECT COUNT(*) FROM {t_name}").fetchone()[0]
    print(f"Table {t_name}: {count} rows")
    if count > 0 and count < 10:
        rows = c.execute(f"SELECT * FROM {t_name}").fetchall()
        print("  Rows:", rows)
