import sqlite3, json
DB="swing_ai.db"

def init_db():
    con=sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        payload TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS journal(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        symbol TEXT, setup TEXT, score REAL, entry REAL, stop REAL,
        target1 REAL, target2 REAL, status TEXT, notes TEXT
    )""")
    con.commit(); con.close()

def save_scan(payload):
    con=sqlite3.connect(DB)
    con.execute("INSERT INTO scans(payload) VALUES(?)",(json.dumps(payload,default=str),))
    con.commit(); con.close()

def add_trade(row):
    con=sqlite3.connect(DB)
    con.execute("""INSERT INTO journal(symbol,setup,score,entry,stop,target1,target2,status,notes)
                   VALUES(?,?,?,?,?,?,?,?,?)""",row)
    con.commit(); con.close()

def trades():
    con=sqlite3.connect(DB)
    import pandas as pd
    df=pd.read_sql_query("SELECT * FROM journal ORDER BY id DESC",con)
    con.close(); return df
