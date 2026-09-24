"""การเชื่อมต่อ Postgres และสร้างตารางตอนเริ่ม"""
import os
from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    trip_no        int NOT NULL,
    origin         jsonb NOT NULL,
    destination    jsonb NOT NULL,
    departure_time timestamptz NOT NULL,
    waypoints      jsonb NOT NULL DEFAULT '[]',
    plan_status    text NOT NULL DEFAULT 'NONE' CHECK (plan_status IN ('NONE', 'FRESH', 'STALE')),
    plan           jsonb,
    UNIQUE (user_id, trip_no)
);
"""

_pool: Optional[ConnectionPool] = None


def init_db(timeout: float = 10) -> None:
    """ต่อฐานข้อมูลแล้วสร้างตาราง ต่อไม่ได้ภายใน timeout ให้ raise เพื่อให้ process จบ"""
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("ยังไม่ได้ตั้งค่า DATABASE_URL ใน .env")
    _pool = ConnectionPool(url, min_size=1, max_size=10, open=False,
                           kwargs={"connect_timeout": 3, "row_factory": dict_row})
    try:
        # pool ลองต่อซ้ำเองจนได้หรือครบ timeout
        _pool.open(wait=True, timeout=timeout)
    except PoolTimeout:
        _pool.close()
        raise RuntimeError(f"ต่อฐานข้อมูลไม่ได้ภายใน {timeout} วินาที")
    with _pool.connection() as conn:
        conn.execute(SCHEMA)


def close_db() -> None:
    if _pool is not None:
        _pool.close()


def connection():
    """ใช้แบบ `with db.connection() as conn:` ออกจาก with แล้ว commit ให้เอง ถ้า error จะ rollback"""
    return _pool.connection()


def create_user(email: str, password_hash: str) -> Optional[dict]:
    """คืน None ถ้าอีเมลนี้มีอยู่แล้ว"""
    with connection() as conn:
        return conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) "
            "ON CONFLICT (email) DO NOTHING RETURNING user_id::text AS user_id, email",
            (email, password_hash),
        ).fetchone()


def find_user_by_email(email: str) -> Optional[dict]:
    """มี password_hash ติดมาด้วย ใช้ตอน login เท่านั้น ห้าม return ออกไปตรงๆ"""
    with connection() as conn:
        return conn.execute(
            "SELECT user_id::text AS user_id, email, password_hash FROM users WHERE email = %s",
            (email,),
        ).fetchone()


def find_user(user_id: str) -> Optional[dict]:
    with connection() as conn:
        return conn.execute(
            "SELECT user_id::text AS user_id, email FROM users WHERE user_id = %s",
            (user_id,),
        ).fetchone()