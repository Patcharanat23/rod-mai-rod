import os

import psycopg
import pytest
from fastapi.testclient import TestClient

# ค่าตั้งต้นสำหรับรันบนเครื่องกับ postgres ใน Docker (พอร์ต 5433) ตั้ง env เองเพื่อเปลี่ยนได้
os.environ.setdefault("DATABASE_URL", "postgresql://rodmairod:changeme@localhost:5433/rodmairod")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app import app  # noqa: E402  ต้อง import หลังตั้ง env


def _db_up() -> bool:
    try:
        psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def client():
    """client ที่ต่อฐานข้อมูลจริง ต่อไม่ได้ให้ข้ามเทสต์นั้น"""
    if not _db_up():
        pytest.skip("ต่อ Postgres ไม่ได้ เปิดด้วย docker compose up -d postgres")
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_header(client):
    res = client.post("/api/v1/auth/login", json={"email": "demo@example.com", "password": "demo1234"})
    return {"Authorization": f"Bearer {res.json()['data']['token']}"}
