import sqlite3
from datetime import datetime, timedelta

DB_NAME = "lms_local.db"

def init_db():
    """Creates the database and the activity table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_activity (
            date TEXT PRIMARY KEY,
            activity_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def log_daily_activity():
    """Adds +1 to today's activity count."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''
        INSERT INTO daily_activity (date, activity_count) 
        VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET activity_count = activity_count + 1
    ''', (today,))
    
    conn.commit()
    conn.close()

def get_weekly_activity():
    """Fetches the activity count for the last 7 days."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    weekly_data = []
    today = datetime.now()
    
    for i in range(6, -1, -1):
        target_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        c.execute('SELECT activity_count FROM daily_activity WHERE date = ?', (target_date,))
        result = c.fetchone()
        
        if result:
            weekly_data.append(result[0])
        else:
            weekly_data.append(0)
            
    conn.close()
    return weekly_data

# --- THE FIX: Auto-Initialize ---
# This guarantees the table is created the millisecond this file is imported,
# before any other functions can crash.
init_db()