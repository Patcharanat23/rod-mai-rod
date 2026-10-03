"""น้ำท่วม GISTDA ใช้ 3 วันก่อน ว่างแล้วใช้ 7 วัน รวมเป็นตำบลทีละหน้า"""
import httpx

import gistda


def cell(tb, lat, lng, road=0):
    ring = [[lng, lat], [lng + 0.01, lat], [lng + 0.01, lat + 0.01], [lng, lat]]
    return {"geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
            "properties": {"pv_tn": "จ.สระแก้ว", "ap_tn": "อ.เมือง", "tb_tn": tb, "f_area": 1600, "length_road": road,
                           "_updatedAt": "2026-10-01T18:10:00.000Z"}}


def fake_client(pages_by_window, monkeypatch):
    asked = []

    def handler(request):
        window = request.url.path.rsplit("/", 1)[-1]
        offset = int(request.url.params["offset"])
        asked.append((window, offset))
        pages = pages_by_window.get(window, [])
        page = pages[offset // gistda.PAGE] if offset // gistda.PAGE < len(pages) else []
        return httpx.Response(200, json={"features": page})

    real = httpx.Client
    monkeypatch.setattr(gistda.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("GISTDA_API_KEY", "k")
    return asked


def test_empty_3days_falls_back_to_7days(monkeypatch):
    asked = fake_client({"7days": [[cell("ต.ท่าเกษม", 13.8, 102.0, road=1500)]]}, monkeypatch)
    found, used = gistda.fetch_all()
    assert used == "7days" and [h["severity"] for h in found] == ["HIGH"]
    assert [w for w, _ in asked] == ["3days", "7days"]


def test_3days_used_when_it_has_data_and_pages_are_grouped(monkeypatch):
    monkeypatch.setattr(gistda, "PAGE", 2)
    pages = [[cell("ต.ก", 13.8, 102.0), cell("ต.ก", 13.81, 102.0)], [cell("ต.ข", 13.9, 102.1, road=200)]]
    asked = fake_client({"3days": pages, "7days": [[cell("ต.ค", 14.0, 102.0)]]}, monkeypatch)
    found, used = gistda.fetch_all()
    assert used == "3days" and asked == [("3days", 0), ("3days", 2)]
    by_tb = {h["hazard_id"].split("-")[-1]: h for h in found}
    assert set(by_tb) == {"ต.ก", "ต.ข"} and by_tb["ต.ข"]["severity"] == "MEDIUM" and by_tb["ต.ข"]["road_cells"]


def test_nothing_anywhere_gives_no_window(monkeypatch):
    fake_client({}, monkeypatch)
    assert gistda.fetch_all() == ([], None)
