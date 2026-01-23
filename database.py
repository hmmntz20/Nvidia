import sqlite3
import json
import time
from config import DB_FILE, CACHE_EXPIRY

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stock_cache
                 (symbol TEXT PRIMARY KEY, data TEXT, timestamp REAL)''')
    conn.commit()
    conn.close()

def load_cache(symbol):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT data, timestamp FROM stock_cache WHERE symbol = ?", (symbol,))
    result = c.fetchone()
    conn.close()
    
    if result:
        data_json, timestamp = result
        if time.time() - timestamp < CACHE_EXPIRY:
            return json.loads(data_json)
    return None

def save_cache(symbol, tech_data, ai_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    full_data = {'tech': tech_data, 'ai': ai_data}
    json_str = json.dumps(full_data)
    c.execute("INSERT OR REPLACE INTO stock_cache (symbol, data, timestamp) VALUES (?, ?, ?)",
              (symbol, json_str, time.time()))
    conn.commit()
    conn.close()