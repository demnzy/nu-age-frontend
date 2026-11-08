import sqlite3
from datetime import datetime, timedelta

DB_NAME = "lms_local.db"
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    """Returns a persistent WAL-enabled SQLite connection for daily activity tracking."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.execute("PRAGMA synchronous = NORMAL")
        _conn.execute("PRAGMA temp_store = MEMORY")
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_activity (
                date TEXT PRIMARY KEY,
                activity_count INTEGER
            )
            """
        )
        _conn.commit()
    return _conn


def init_db():
    """Creates the database and the activity table if they don't exist."""
    _get_conn()


def log_daily_activity():
    """Adds +1 to today's activity count."""
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        """
        INSERT INTO daily_activity (date, activity_count)
        VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET activity_count = activity_count + 1
        """,
        (today,),
    )
    conn.commit()


def get_weekly_activity():
    """Fetches the activity count for the last 7 days in a single SQL query."""
    conn = _get_conn()
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    rows = conn.execute(
        "SELECT date, activity_count FROM daily_activity WHERE date >= ?",
        (dates[0],),
    ).fetchall()
    counts_by_date = {r[0]: (r[1] or 0) for r in rows}
    return [counts_by_date.get(d, 0) for d in dates]


# --- THE FIX: Auto-Initialize ---
# This guarantees the table is created the millisecond this file is imported,
# before any other functions can crash.
init_db()