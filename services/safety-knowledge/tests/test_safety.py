from fastapi.testclient import TestClient

from app import CONTACTS, app, load_docs

client = TestClient(app)


def test_every_doc_has_title_source_and_known_hazards():
    for doc in load_docs():
        assert doc["title_th"] and doc["source"], doc["doc_id"]
        assert doc["lines"], doc["doc_id"]
        assert set(doc["hazard_types"]) <= {"RAIN", "HEAVY_RAIN", "STRONG_WIND", "FLOOD", "LANDSLIDE_RISK", "STORM", "EARTHQUAKE"}


def test_search_filters_by_hazard_type():
    res = client.post("/api/v1/safety/search", json={"query": "น้ำ", "hazard_types": ["FLOOD"]}).json()
    assert res["error"] is None
    assert res["data"]["results"]
    assert all(r["doc_id"] == "flood" for r in res["data"]["results"])


def test_empty_query_is_validation_error():
    res = client.post("/api/v1/safety/search", json={"query": "  "})
    assert res.status_code == 400


def test_emergency_always_has_contacts():
    data = client.get("/api/v1/safety/emergency", params={"hazard_type": "FLOOD"}).json()["data"]
    assert data["steps_th"] and data["contacts"] == CONTACTS


def test_unknown_hazard_type_is_rejected():
    res = client.get("/api/v1/safety/emergency", params={"hazard_type": "ZOMBIE"})
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
