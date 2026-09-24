import json

import pytest

import app as routing


def saved(stops) -> dict:
    """คำตอบ OSRM ที่บันทึกไว้ใน fixtures/ ของทริปนี้ (ไฟล์เดียวกับที่ DEMO_MODE ใช้)"""
    return json.loads(routing.fixture_path(routing.route_key(stops)).read_text())


@pytest.fixture(autouse=True)
def offline_osrm(monkeypatch):
    """เทสต์ห้ามยิง OSRM จริง ใช้คำตอบที่บันทึกไว้แทน และเริ่มทุกเทสต์ด้วย cache ว่าง"""
    monkeypatch.setattr(routing, "osrm_request", saved)
    monkeypatch.setenv("OSRM_BASE_URL", "http://osrm.test")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    routing._cache.clear()
    routing._pending.clear()
