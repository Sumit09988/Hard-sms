import sqlite3
from datetime import date

DAILY_FREE = 5
REFER_REWARD = 2

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  credits INTEGER DEFAULT 5,
                  last_reset DATE,
                  referrer_id INTEGER,
                  total_sent INTEGER DEFAULT 0,
                  phone_number TEXT,
                  join_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (referrer_id INTEGER, referred_id INTEGER, date DATE)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("INSERT INTO users (user_id, username, credits, last_reset, referrer_id, join_date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, username, DAILY_FREE, today, referrer_id, today))
    if referrer_id:
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (REFER_REWARD, referrer_id))
        c.execute("INSERT INTO referrals VALUES (?, ?, ?)", (referrer_id, user_id, today))
    conn.commit()
    conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def update_phone(user_id, phone):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET phone_number = ? WHERE user_id=?", (phone, user_id))
    conn.commit()
    conn.close()

def get_user_phone(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT phone_number FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_sent_count(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET total_sent = total_sent + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def check_daily_reset():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("SELECT user_id, last_reset FROM users")
    users = c.fetchall()
    for user_id, last_reset in users:
        if last_reset is None or str(last_reset) != str(today):
            c.execute("UPDATE users SET credits = ?, last_reset = ? WHERE user_id=?", (DAILY_FREE, today, user_id))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_today_new_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    today = date.today()
    c.execute("SELECT COUNT(*) FROM users WHERE join_date=?", (today,))
    count = c.fetchone()[0]
    conn.close()
    return count
