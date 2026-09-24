import json
from pathlib import Path

import pytest

import app as routing

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
# คำตอบ OSRM ที่บันทึกไว้ key คือพิกัด stop ทุกจุดปัด 3 ตำแหน่ง
SAVED = {
    ((13.756, 100.502), (18.788, 98.985)): "bkk_cnx.json",
    ((13.756, 100.502), (15.705, 100.137), (18.788, 98.985)): "bkk_nsn_cnx.json",
}


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def offline_osrm(monkeypatch):
    """เทสต์ห้ามยิง OSRM จริง ใช้คำตอบที่บันทึกไว้แทน"""
    def fake(stops):
        return load(SAVED[tuple((round(s.lat, 3), round(s.lng, 3)) for s in stops)])
    monkeypatch.setattr(routing, "osrm_request", fake)
