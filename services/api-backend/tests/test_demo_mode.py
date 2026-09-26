import json

import pytest

import places

CNX_CELL = "18.79_98.99"
BKK_PLACE = {"name": "กรุงเทพมหานคร", "detail": "กรุงเทพมหานคร", "lat": 13.7525, "lng": 100.4935}
GATE = {"name": "ประตูท่าแพ", "detail": None, "lat": 18.7877, "lng": 98.9933, "kind_th": "สถานที่ท่องเที่ยว"}


@pytest.fixture(autouse=True)
def demo(monkeypatch, tmp_path):
    """เปิด DEMO_MODE ใช้ไฟล์บันทึกชั่วคราว และทำให้เทสต์พังทันทีถ้ามีการเรียกเน็ต"""
    monkeypatch.setenv("DEMO_MODE", "true")
    search_file, nearby_file = tmp_path / "search.json", tmp_path / "nearby.json"
    search_file.write_text(json.dumps({"queries": {"กรุงเทพมหานคร": [BKK_PLACE]}}), encoding="utf-8")
    nearby_file.write_text(json.dumps({"cells": {CNX_CELL: [GATE]}}), encoding="utf-8")
    monkeypatch.setattr("places.SEARCH_FIXTURE", search_file)
    monkeypatch.setattr("places.NEARBY_FIXTURE", nearby_file)

    def no_network(*args, **kwargs):
        raise AssertionError("DEMO_MODE ห้ามเรียกเน็ต")

    monkeypatch.setattr("places.httpx.get", no_network)
    monkeypatch.setattr("places.httpx.post", no_network)
    places._cache.clear()
    places._nearby_cache.clear()


def test_search_reads_saved_answer_without_network():
    assert places.search("กทม") == [BKK_PLACE]
    assert places.search("กรุงเทพ") == [BKK_PLACE]


def test_search_unknown_query_is_empty_not_error():
    assert places.search("ภูเก็ต") == []


def test_nearby_uses_nearest_saved_cell_within_15_km():
    assert places.nearby(18.79, 98.98) == [GATE]
    assert places.nearby(18.85, 98.95) == [GATE]  # ห่างช่องที่บันทึกไว้ประมาณ 8 กม.


def test_nearby_without_saved_cell_nearby_is_empty():
    assert places.nearby(7.88, 98.39) == []  # ภูเก็ต ไกลทุกช่องที่บันทึกไว้


def test_committed_fixtures_cover_demo_path():
    # ไฟล์จริงที่ record_fixtures.py บันทึกและ commit ไว้ ต้องครอบคลุมเส้นสาธิต
    queries = json.loads(places.FIXTURES.joinpath("places_search.json").read_text(encoding="utf-8"))["queries"]
    for word in ("กทม", "เชียงใหม่", "นครสวรรค์"):
        assert queries.get(places.expand(word).lower()), word
    cells = json.loads(places.FIXTURES.joinpath("places_nearby.json").read_text(encoding="utf-8"))["cells"]
    assert len(cells) == 3