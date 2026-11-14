import aiosqlite, os
from config import DB_PATH

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.',exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, balance INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT UNIQUE NOT NULL, payment_id TEXT UNIQUE, tg_id INTEGER NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP, paid_at TEXT);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, kind TEXT NOT NULL, details TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, amount INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        await db.commit()

async def upsert_user(u):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO users(tg_id,username,full_name) VALUES(?,?,?) ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name',(u.id,u.username or '',u.full_name or ''))
        await db.commit()

async def get_user(tg):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        cur=await db.execute('SELECT * FROM users WHERE tg_id=?',(tg,)); return await cur.fetchone()

async def create_payment(order,tg,amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO payments(order_id,tg_id,amount) VALUES(?,?,?)',(order,tg,amount)); await db.commit()

async def set_payment_id(order,pid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET payment_id=? WHERE order_id=? AND status='pending'",(pid,order)); await db.commit()

async def payment_by_order(order):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row; c=await db.execute('SELECT * FROM payments WHERE order_id=?',(order,)); return await c.fetchone()

async def payment_by_id(pid):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row; c=await db.execute('SELECT * FROM payments WHERE payment_id=?',(pid,)); return await c.fetchone()

async def mark_paid(pid,amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('BEGIN IMMEDIATE')
        c=await db.execute("SELECT * FROM payments WHERE payment_id=?",(pid,)); p=await c.fetchone()
        if not p or p[4] != amount:
            await db.rollback(); return None,False
        if p[5]=='paid':
            c=await db.execute('SELECT balance FROM users WHERE tg_id=?',(p[3],)); row=await c.fetchone(); await db.commit(); return (dict(tg_id=p[3],amount=p[4],balance=row[0] if row else 0),False)
        await db.execute("UPDATE payments SET status='paid',paid_at=CURRENT_TIMESTAMP WHERE payment_id=?",(pid,))
        await db.execute('UPDATE users SET balance=balance+? WHERE tg_id=?',(amount,p[3]))
        await db.execute('INSERT INTO transactions(tg_id,amount,kind,note) VALUES(?,?,?,?)',(p[3],amount,'topup','HamyonAPI'))
        c=await db.execute('SELECT balance FROM users WHERE tg_id=?',(p[3],)); b=(await c.fetchone())[0]
        await db.commit(); return (dict(tg_id=p[3],amount=amount,balance=b),True)

async def add_request(tg,kind,details,amount=0):
    async with aiosqlite.connect(DB_PATH) as db:
        c=await db.execute('INSERT INTO requests(tg_id,kind,details,amount) VALUES(?,?,?,?)',(tg,kind,details,amount)); await db.commit(); return c.lastrowid

async def balance(tg):
    u=await get_user(tg); return u['balance'] if u else 0
