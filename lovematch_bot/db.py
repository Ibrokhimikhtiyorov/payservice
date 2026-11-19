import logging
from datetime import datetime, timezone

import asyncpg

from config import DAILY_LIKES_FREE, DATABASE_URL, DEFAULT_CHAT_PRICE, DEFAULT_PREMIUM_PRICES

log = logging.getLogger(__name__)
pool: asyncpg.Pool | None = None


async def init_pool():
    global pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL .env da yo'q")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                tg_id BIGINT PRIMARY KEY,
                name TEXT,
                age INT,
                gender TEXT,
                city TEXT,
                photo_id TEXT,
                bio TEXT,
                looking_for TEXT,
                lang TEXT NOT NULL DEFAULT 'uz',
                is_banned BOOLEAN NOT NULL DEFAULT FALSE,
                is_premium BOOLEAN NOT NULL DEFAULT FALSE,
                premium_until TIMESTAMPTZ,
                is_vip BOOLEAN NOT NULL DEFAULT FALSE,
                boost_until TIMESTAMPTZ,
                daily_likes INT NOT NULL DEFAULT 0,
                likes_day DATE,
                reg_done BOOLEAN NOT NULL DEFAULT FALSE,
                last_active TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS search_prefs (
                tg_id BIGINT PRIMARY KEY REFERENCES users(tg_id) ON DELETE CASCADE,
                pref_gender TEXT,
                pref_city TEXT,
                age_min INT,
                age_max INT
            );
            CREATE TABLE IF NOT EXISTS likes (
                from_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                to_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                is_super BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY(from_id, to_id)
            );
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                user_a BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                user_b BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                is_paid BOOLEAN NOT NULL DEFAULT FALSE,
                paid_by BIGINT,
                paid_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(user_a, user_b)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                match_id INT REFERENCES matches(id) ON DELETE CASCADE,
                sender_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL,
                purpose TEXT NOT NULL,
                amount INT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                provider_ref TEXT UNIQUE,
                payment_id TEXT UNIQUE,
                match_id INT REFERENCES matches(id) ON DELETE SET NULL,
                meta TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                paid_at TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS blocks (
                blocker_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                blocked_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY(blocker_id, blocked_id)
            );
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                reporter_id BIGINT,
                reported_id BIGINT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_likes_to ON likes(to_id);
            CREATE INDEX IF NOT EXISTS idx_matches_users ON matches(user_a, user_b);
            CREATE INDEX IF NOT EXISTS idx_messages_match ON messages(match_id);
            CREATE INDEX IF NOT EXISTS idx_payments_ref ON payments(provider_ref);
            """
        )
        # migration for existing DBs
        await conn.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_id TEXT UNIQUE")
        await conn.execute(
            "INSERT INTO settings(key,value) VALUES('chat_price',$1) ON CONFLICT(key) DO NOTHING",
            str(DEFAULT_CHAT_PRICE),
        )
        for k, v in DEFAULT_PREMIUM_PRICES.items():
            await conn.execute(
                "INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO NOTHING",
                f"premium_{k}", str(v),
            )
    log.info("DB initialized")


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def fetchval(q, *args):
    async with pool.acquire() as conn:
        return await conn.fetchval(q, *args)


async def fetchrow(q, *args):
    async with pool.acquire() as conn:
        return await conn.fetchrow(q, *args)


async def fetch(q, *args):
    async with pool.acquire() as conn:
        return await conn.fetch(q, *args)


async def execute(q, *args):
    async with pool.acquire() as conn:
        return await conn.execute(q, *args)


async def get_setting(key: str, default: str = "") -> str:
    v = await fetchval("SELECT value FROM settings WHERE key=$1", key)
    return v if v is not None else default


async def set_setting(key: str, value: str):
    await execute(
        "INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
        key, str(value),
    )


async def ensure_user(tg_id: int, lang: str = "uz"):
    await execute(
        "INSERT INTO users(tg_id, lang) VALUES($1,$2) ON CONFLICT(tg_id) DO UPDATE SET last_active=NOW()",
        tg_id, lang,
    )
    await execute(
        "INSERT INTO search_prefs(tg_id) VALUES($1) ON CONFLICT(tg_id) DO NOTHING",
        tg_id,
    )


async def get_user(tg_id: int):
    return await fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)


async def set_user_lang(tg_id: int, lang: str):
    await execute("UPDATE users SET lang=$2 WHERE tg_id=$1", tg_id, lang)


async def upsert_profile(tg_id: int, **fields):
    if not fields:
        return
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(keys))
    vals = [fields[k] for k in keys]
    await execute(f"UPDATE users SET {sets}, last_active=NOW() WHERE tg_id=$1", tg_id, *vals)


async def is_registered(tg_id: int) -> bool:
    row = await fetchrow("SELECT reg_done FROM users WHERE tg_id=$1", tg_id)
    return bool(row and row["reg_done"])


def pair(a: int, b: int):
    return (a, b) if a < b else (b, a)


async def is_blocked_either(a: int, b: int) -> bool:
    v = await fetchval(
        "SELECT 1 FROM blocks WHERE (blocker_id=$1 AND blocked_id=$2) OR (blocker_id=$2 AND blocked_id=$1) LIMIT 1",
        a, b,
    )
    return bool(v)


async def add_like(from_id: int, to_id: int, is_super: bool = False) -> bool:
    await execute(
        "INSERT INTO likes(from_id,to_id,is_super) VALUES($1,$2,$3) ON CONFLICT(from_id,to_id) DO UPDATE SET is_super=likes.is_super OR EXCLUDED.is_super",
        from_id, to_id, is_super,
    )
    mutual = await fetchval("SELECT 1 FROM likes WHERE from_id=$1 AND to_id=$2", to_id, from_id)
    if mutual:
        a, b = pair(from_id, to_id)
        res = await fetchval(
            "INSERT INTO matches(user_a,user_b) VALUES($1,$2) ON CONFLICT(user_a,user_b) DO NOTHING RETURNING id",
            a, b,
        )
        return res is not None
    return False


async def get_next_profile(tg_id: int):
    q = """
    SELECT u.* FROM users u
    LEFT JOIN search_prefs p ON p.tg_id=$1
    WHERE u.tg_id <> $1 AND u.reg_done=TRUE AND u.is_banned=FALSE
      AND NOT EXISTS (SELECT 1 FROM likes l WHERE l.from_id=$1 AND l.to_id=u.tg_id)
      AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.blocker_id=$1 AND b.blocked_id=u.tg_id) OR (b.blocker_id=u.tg_id AND b.blocked_id=$1))
      AND (p.pref_gender IS NULL OR p.pref_gender='' OR u.gender=p.pref_gender)
      AND (p.pref_city IS NULL OR p.pref_city='' OR lower(u.city)=lower(p.pref_city))
      AND (p.age_min IS NULL OR u.age >= p.age_min)
      AND (p.age_max IS NULL OR u.age <= p.age_max)
    ORDER BY (u.boost_until > NOW()) DESC, RANDOM()
    LIMIT 1
    """
    return await fetchrow(q, tg_id)


async def who_liked_me(tg_id: int):
    return await fetch(
        """
        SELECT u.* FROM likes l JOIN users u ON u.tg_id=l.from_id
        WHERE l.to_id=$1 AND u.reg_done=TRUE
          AND NOT EXISTS (SELECT 1 FROM blocks b WHERE (b.blocker_id=$1 AND b.blocked_id=u.tg_id) OR (b.blocker_id=u.tg_id AND b.blocked_id=$1))
        ORDER BY l.is_super DESC, l.created_at DESC LIMIT 50
        """,
        tg_id,
    )


async def get_matches(tg_id: int):
    return await fetch(
        """
        SELECT m.*, u.tg_id as other_id, u.name, u.photo_id, u.city, u.age
        FROM matches m
        JOIN users u ON u.tg_id = CASE WHEN m.user_a=$1 THEN m.user_b ELSE m.user_a END
        WHERE m.user_a=$1 OR m.user_b=$1
        ORDER BY m.created_at DESC
        """,
        tg_id,
    )


async def get_match(match_id: int):
    return await fetchrow("SELECT * FROM matches WHERE id=$1", match_id)


async def get_match_between(a: int, b: int):
    x, y = pair(a, b)
    return await fetchrow("SELECT * FROM matches WHERE user_a=$1 AND user_b=$2", x, y)


async def create_payment(tg_id: int, purpose: str, amount: int, provider_ref: str, match_id: int | None = None, meta: str = ""):
    return await fetchrow(
        """
        INSERT INTO payments(tg_id,purpose,amount,status,provider_ref,match_id,meta)
        VALUES($1,$2,$3,'pending',$4,$5,$6)
        ON CONFLICT(provider_ref) DO NOTHING
        RETURNING *
        """,
        tg_id, purpose, amount, provider_ref, match_id, meta,
    )


async def get_payment_by_ref(provider_ref: str):
    return await fetchrow("SELECT * FROM payments WHERE provider_ref=$1", provider_ref)


async def get_payment_by_payment_id(payment_id: str):
    return await fetchrow("SELECT * FROM payments WHERE payment_id=$1", payment_id)


async def get_payment(payment_id: int):
    return await fetchrow("SELECT * FROM payments WHERE id=$1", payment_id)


async def set_payment_id(provider_ref: str, payment_id: str):
    await execute(
        "UPDATE payments SET payment_id=$2 WHERE provider_ref=$1 AND status='pending'",
        provider_ref, payment_id,
    )


async def confirm_payment(provider_ref: str) -> tuple[bool, dict | None, bool]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            p = await conn.fetchrow("SELECT * FROM payments WHERE provider_ref=$1 FOR UPDATE", provider_ref)
            if not p:
                return False, None, False
            if p["status"] == "paid":
                return True, dict(p), False
            await conn.execute("UPDATE payments SET status='paid', paid_at=NOW() WHERE id=$1", p["id"])
            if p["purpose"] == "chat_unlock" and p["match_id"]:
                await conn.execute(
                    "UPDATE matches SET is_paid=TRUE, paid_by=$2, paid_at=NOW() WHERE id=$1 AND is_paid=FALSE",
                    p["match_id"], p["tg_id"],
                )
            elif p["purpose"].startswith("premium_"):
                plan = p["purpose"].split("_", 1)[1]
                days = 7 if plan == "week" else 30 if plan == "month" else 90
                vip = plan == "vip"
                await conn.execute(
                    """
                    UPDATE users SET is_premium=TRUE, is_vip = (is_vip OR $3),
                        premium_until = GREATEST(COALESCE(premium_until,NOW()), NOW()) + ($2 || ' days')::interval
                    WHERE tg_id=$1
                    """,
                    p["tg_id"], str(days), vip,
                )
            elif p["purpose"] == "boost":
                await conn.execute(
                    "UPDATE users SET boost_until = GREATEST(COALESCE(boost_until,NOW()), NOW()) + interval '24 hours' WHERE tg_id=$1",
                    p["tg_id"],
                )
            p2 = await conn.fetchrow("SELECT * FROM payments WHERE id=$1", p["id"])
            return True, dict(p2), True


async def add_message(match_id: int, sender_id: int, text: str):
    await execute("INSERT INTO messages(match_id,sender_id,text) VALUES($1,$2,$3)", match_id, sender_id, text)


async def get_chat_messages(match_id: int, limit: int = 30):
    return await fetch(
        "SELECT * FROM messages WHERE match_id=$1 ORDER BY id DESC LIMIT $2",
        match_id, limit,
    )


async def add_report(reporter_id: int, reported_id: int, reason: str):
    await execute("INSERT INTO reports(reporter_id,reported_id,reason) VALUES($1,$2,$3)", reporter_id, reported_id, reason)


async def add_block(blocker_id: int, blocked_id: int):
    await execute("INSERT INTO blocks(blocker_id,blocked_id) VALUES($1,$2) ON CONFLICT DO NOTHING", blocker_id, blocked_id)


async def stats():
    users = await fetchval("SELECT COUNT(*) FROM users") or 0
    active = await fetchval("SELECT COUNT(*) FROM users WHERE last_active > NOW() - interval '7 days'") or 0
    revenue = await fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'") or 0
    chat_pay = await fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND purpose='chat_unlock'") or 0
    prem_pay = await fetchval("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND purpose LIKE 'premium_%'") or 0
    matches = await fetchval("SELECT COUNT(*) FROM matches") or 0
    return {
        "users": users, "active": active, "revenue": revenue,
        "chat_pay": chat_pay, "prem_pay": prem_pay, "matches": matches,
    }


async def list_payments(limit: int = 30):
    return await fetch("SELECT * FROM payments ORDER BY id DESC LIMIT $1", limit)


async def list_reports(limit: int = 30):
    return await fetch("SELECT * FROM reports ORDER BY id DESC LIMIT $1", limit)


async def list_users(limit: int = 30):
    return await fetch("SELECT tg_id,name,age,city,is_banned,is_premium,created_at FROM users ORDER BY created_at DESC LIMIT $1", limit)


async def set_banned(tg_id: int, banned: bool = True):
    await execute("UPDATE users SET is_banned=$2 WHERE tg_id=$1", tg_id, banned)


async def can_like(tg_id: int) -> bool:
    u = await get_user(tg_id)
    if not u:
        return False
    if u["is_premium"] and (u["premium_until"] is None or u["premium_until"] > datetime.now(timezone.utc)):
        return True
    today = datetime.now(timezone.utc).date()
    day = u["likes_day"]
    count = u["daily_likes"] or 0
    if day != today:
        await execute("UPDATE users SET likes_day=$2, daily_likes=0 WHERE tg_id=$1", tg_id, today)
        return True
    return count < DAILY_LIKES_FREE


async def inc_like(tg_id: int):
    today = datetime.now(timezone.utc).date()
    await execute(
        "UPDATE users SET likes_day=$2, daily_likes = CASE WHEN likes_day=$2 THEN daily_likes+1 ELSE 1 END WHERE tg_id=$1",
        tg_id, today,
    )


async def get_search_prefs(tg_id: int):
    return await fetchrow("SELECT * FROM search_prefs WHERE tg_id=$1", tg_id)


async def set_search_prefs(tg_id: int, pref_gender=None, pref_city=None, age_min=None, age_max=None):
    await execute(
        """
        INSERT INTO search_prefs(tg_id,pref_gender,pref_city,age_min,age_max)
        VALUES($1,$2,$3,$4,$5)
        ON CONFLICT(tg_id) DO UPDATE SET
          pref_gender=EXCLUDED.pref_gender,
          pref_city=EXCLUDED.pref_city,
          age_min=EXCLUDED.age_min,
          age_max=EXCLUDED.age_max
        """,
        tg_id, pref_gender, pref_city, age_min, age_max,
    )


async def touch_active(tg_id: int):
    await execute("UPDATE users SET last_active=NOW() WHERE tg_id=$1", tg_id)
