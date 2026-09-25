import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

import places
from envelope import ApiError

CNX = (18.79, 98.98)


def node(name, lat, lng, **tags):
    return {"type": "node", "lat": lat, "lon": lng, "tags": {"name": name, **tags}}


@pytest.fixture(autouse=True)
def empty_cache():
    places._nearby_cache.clear()


@pytest.fixture
def overpass(monkeypatch):
    """แทน Overpass จริง เทสต์ไม่ยิงเน็ต คืน list ของคำขอที่ถูกส่งไปให้ตรวจ"""
    sent = []

    def use(elements=(), error=None, body=None, delay=0):
        def fake_post(url, data=None, headers=None, timeout=None):
            sent.append({"data": data, "headers": headers, "timeout": timeout})
            time.sleep(delay)
            if error is not None:
                raise error
            request = httpx.Request("POST", url)
            if body is not None:
                return httpx.Response(200, content=body, request=request)
            return httpx.Response(200, json={"elements": list(elements)}, request=request)

        monkeypatch.setattr("places.httpx.post", fake_post)
        return sent

    return use


def test_one_request_with_radius_timeout_and_user_agent(overpass):
    sent = overpass()
    places.nearby(*CNX)
    assert len(sent) == 1
    query = sent[0]["data"]["data"]
    assert "around:5000,18.79,98.98" in query
    assert "attraction|viewpoint|museum|zoo|theme_park" in query
    assert "monument|temple|ruins" in query
    assert sent[0]["timeout"] == 8
    assert "rod-mai-rod" in sent[0]["headers"]["User-Agent"]


def test_nearest_first_and_at_most_8(overpass):
    # วัด 10 แห่งห่างออกไปทางเหนือทีละประมาณ 200 ม. ส่งมาแบบกลับลำดับ
    overpass([node(f"วัด {i}", 18.79 + i * 0.002, 98.98, historic="temple") for i in reversed(range(10))])
    found = places.nearby(*CNX)
    assert [p["name"] for p in found] == [f"วัด {i}" for i in range(8)]


def test_name_th_is_preferred_and_detail_comes_from_addr(overpass):
    overpass([
        node("Tha Phae Gate", 18.7877, 98.9933, **{"name:th": "ประตูท่าแพ", "tourism": "attraction"}),
        node("Old City View", 18.80, 98.97, tourism="viewpoint",
             **{"addr:district": "อำเภอเมืองเชียงใหม่", "addr:province": "เชียงใหม่"}),
    ])
    found = places.nearby(*CNX)
    gate = next(p for p in found if p["name"] == "ประตูท่าแพ")
    assert list(gate) == ["name", "detail", "lat", "lng", "kind_th"]
    assert gate == {"name": "ประตูท่าแพ", "detail": None, "lat": 18.7877, "lng": 98.9933, "kind_th": "สถานที่ท่องเที่ยว"}
    view = next(p for p in found if p["kind_th"] == "จุดชมวิว")
    assert view["detail"] == "อำเภอเมืองเชียงใหม่, เชียงใหม่"


def test_every_kind_has_thai_label(overpass):
    tags = [("tourism", "attraction", "สถานที่ท่องเที่ยว"), ("tourism", "viewpoint", "จุดชมวิว"),
            ("tourism", "museum", "พิพิธภัณฑ์"), ("tourism", "zoo", "สวนสัตว์"),
            ("tourism", "theme_park", "สวนสนุก"), ("historic", "monument", "อนุสาวรีย์"),
            ("historic", "temple", "วัด"), ("historic", "ruins", "โบราณสถาน")]
    overpass([node(f"ที่ {i}", 18.79 + i * 0.001, 98.98, **{key: value}) for i, (key, value, _) in enumerate(tags)])
    found = places.nearby(*CNX)
    assert [p["kind_th"] for p in found] == [label for _, _, label in tags]


def test_same_cell_is_cached_for_24_hours(overpass, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("places.monotonic", lambda: now[0])
    sent = overpass([node("ประตูท่าแพ", 18.7877, 98.9933, tourism="attraction")])
    places.nearby(18.791, 98.981)
    places.nearby(18.788, 98.979)  # ปัดแล้วเป็น 18.79, 98.98 ช่องเดียวกัน
    assert len(sent) == 1
    places.nearby(18.83, 98.98)  # คนละช่อง
    assert len(sent) == 2
    now[0] += 24 * 60 * 60 + 1
    places.nearby(18.791, 98.981)
    assert len(sent) == 3


def test_outside_thailand_is_rejected_without_calling_overpass(overpass):
    sent = overpass()
    with pytest.raises(ApiError) as e:
        places.nearby(35.68, 139.76)
    assert e.value.code == "OUT_OF_THAILAND"
    assert sent == []


@pytest.mark.parametrize("broken", [{"error": httpx.ConnectError("down")}, {"body": b"<html>busy</html>"}])
def test_overpass_down_or_bad_json_is_upstream_error(overpass, broken):
    overpass(**broken)
    with pytest.raises(ApiError) as e:
        places.nearby(*CNX)
    assert e.value.code == "UPSTREAM_ERROR"


def test_overpass_slow_is_upstream_timeout_and_not_cached(overpass):
    overpass(error=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiError) as e:
        places.nearby(*CNX)
    assert e.value.code == "UPSTREAM_TIMEOUT"
    sent = overpass([node("ประตูท่าแพ", 18.7877, 98.9933, tourism="attraction")])
    assert len(places.nearby(*CNX)) == 1
    # ครั้งที่ timeout ไม่ถูก cache จึงยิงใหม่เป็นครั้งที่ 2 (sent ใช้ list เดียวกันทั้งเทสต์)
    assert len(sent) == 2


def test_endpoint_needs_login(client, auth_header, overpass):
    overpass([node("ประตูท่าแพ", 18.7877, 98.9933, tourism="attraction")])
    url = "/api/v1/places/nearby"
    params = {"lat": 18.79, "lng": 98.98}
    assert client.get(url, params=params).status_code == 401
    res = client.get(url, params=params, headers=auth_header)
    assert res.status_code == 200
    assert res.json()["data"]["places"][0]["name"] == "ประตูท่าแพ"
    assert client.get(url, params={"lat": 35.68, "lng": 139.76}, headers=auth_header).status_code == 422


def test_concurrent_requests_in_same_cell_call_overpass_once(overpass):
    # จำลองสิ่งที่เจอใน log: หน้าเว็บยิงช่องเดียวกัน 2 คำขอพร้อมกันตอน Overpass ยังตอบไม่เสร็จ
    sent = overpass([node("ประตูท่าแพ", 18.7877, 98.9933, tourism="attraction")], delay=0.3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda p: places.nearby(*p), [(18.791, 98.981), (18.788, 98.979)]))
    assert len(sent) == 1
    assert results[0] == results[1]