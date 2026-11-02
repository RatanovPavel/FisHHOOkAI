import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS premium_users 
                      (session_id TEXT PRIMARY KEY, is_pro BOOLEAN, expire_date DATETIME)''')
    conn.commit()
    conn.close()

def activate_premium(session_id, days=30):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    expire = datetime.now() + timedelta(days=days)
    cursor.execute("INSERT OR REPLACE INTO premium_users VALUES (?, ?, ?)", 
                   (session_id, True, expire))
    conn.commit()
    conn.close()

def check_pro_status(session_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_pro FROM premium_users WHERE session_id=?", (session_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else False
