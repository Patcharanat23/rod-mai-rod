import json

from fastapi.testclient import TestClient

import app as agent
import llm
import tools
from envelope import ApiError
from test_rules import AUTH, FakeBackend, trip

BKK = {"lat": 13.7563, "lng": 100.5018, "name": "กรุงเทพมหานคร"}
CNX = {"lat": 18.7883, "lng": 98.9853, "name": None}


def full_trip(no, departure, plan=None):
    return {**trip(no, departure, plan), "origin": BKK, "destination": CNX}


def run(name, args, backend):
    return tools.run(name, args, backend, AUTH)


def test_list_trips_gives_thai_time_and_place_names():
    out, actions = run("list_trips", {}, FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")]))
    t = out["trips"][0]
    assert t["name"] == "Trip 01" and t["departure_th"] == "5 ม.ค. 08:00 น."
    assert t["origin"] == "กรุงเทพมหานคร" and t["destination"] == "18.788, 98.985"
    assert actions == []


def test_update_time_uses_thai_date_then_replans():
    # 01:00 ไทย ของวันที่ 6 คือ 18:00 UTC ของวันที่ 5
    be = FakeBackend([full_trip(1, "2030-01-05T18:00:00Z")])
    out, actions = run("update_trip_time", {"trip_no": 1, "time": "13:00"}, be)
    assert be.patched() == [{"departure_time": "2030-01-06T06:00:00Z"}]
    assert ("POST", "/api/v1/trips/id-1/plan", None) in be.calls
    assert out["updated"] and out["plan"]["risk_th"] == "ต่ำ"
    assert actions == [{"type": "TRIP_UPDATED", "trip_id": "id-1", "trip_no": 1}]


def test_update_next_day_keeps_time_and_accepts_string_trip_no():
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    run("update_trip_time", {"trip_no": "01", "shift_days": 1}, be)
    assert be.patched() == [{"departure_time": "2030-01-06T01:00:00Z"}]


def test_update_by_hours_needs_no_original_time():
    # 22:00 ไทย เลื่อนออกไป 3 ชม. ข้ามไปวันถัดไป
    be = FakeBackend([full_trip(1, "2030-01-05T15:00:00Z")])
    out, _ = run("update_trip_time", {"trip_no": 1, "shift_hours": 3}, be)
    assert be.patched() == [{"departure_time": "2030-01-05T18:00:00Z"}] and out["departure_th"] == "6 ม.ค. 01:00 น."
    be = FakeBackend([full_trip(1, "2030-01-05T15:00:00Z")])
    run("update_trip_time", {"trip_no": 1, "shift_hours": -2}, be)
    assert be.patched() == [{"departure_time": "2030-01-05T13:00:00Z"}]


def test_update_rejects_past_same_and_bad_input_without_patching():
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    for args in ({"trip_no": 1}, {"trip_no": 1, "time": "25:00"}, {"trip_no": 1, "shift_days": -3},
                 {"trip_no": 1, "shift_days": "x"}, {"trip_no": 1, "shift_hours": 400}):
        out, actions = run("update_trip_time", args, be)
        assert "error" in out and actions == []
    past = FakeBackend([full_trip(1, "2020-01-05T01:00:00Z")])
    out, _ = run("update_trip_time", {"trip_no": 1, "shift_days": 1}, past)
    assert "ผ่านไปแล้ว" in out["error"]
    assert be.patched() == [] and past.patched() == []


def test_unknown_or_ambiguous_trip_asks_back():
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z"), full_trip(2, "2030-01-07T01:00:00Z")])
    out, actions = run("update_trip_time", {"shift_days": 1}, be)
    assert "หมายถึงทริปไหน" in out["error"] and actions == []
    out, _ = run("plan_trip", {"trip_no": 9}, be)
    assert "ไม่เจอ Trip 09" in out["error"]
    assert be.patched() == []


def test_patch_rejected_gives_error_and_no_action():
    def backend(method, path, auth, json=None):
        if method == "GET":
            return [full_trip(1, "2030-01-05T01:00:00Z")]
        raise ApiError("FORBIDDEN", "ไม่ใช่ทริปของคุณ")

    out, actions = run("update_trip_time", {"trip_no": 1, "shift_days": 1}, backend)
    assert out == {"error": "ไม่ใช่ทริปของคุณ", "code": "FORBIDDEN"} and actions == []


def test_plan_failure_after_patch_still_reports_the_update():
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")], plan_fails=True)
    out, actions = run("update_trip_time", {"trip_no": 1, "shift_days": 1}, be)
    assert out["updated"] and "plan_error" in out and len(actions) == 1


def test_weather_needs_a_plan_and_returns_system_numbers():
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    out, _ = run("get_trip_weather", {"trip_no": 1}, be)
    assert "ยังไม่ได้วางแผน" in out["error"]
    forecast = {"rain_mm_per_h": 12.5, "wind_kmh": 20, "temp_c": 26, "condition_th": "ฝนหนัก"}
    plan = {"risk_level": "HIGH", "summary_th": "ฝนหนัก", "waypoints": [
        {"name": "นครสวรรค์", "eta": "2030-01-05T04:00:00Z", "forecast": forecast, "risk_level": "HIGH"}]}
    out, _ = run("get_trip_weather", {"trip_no": 1}, FakeBackend([full_trip(1, "2030-01-05T01:00:00Z", plan)]))
    assert out["risk_th"] == "สูง" and out["waypoints"][0]["forecast"] == forecast
    assert out["waypoints"][0]["eta_th"] == "5 ม.ค. 11:00 น."


def test_unknown_tool_and_bad_arguments():
    assert "error" in run("delete_everything", {}, FakeBackend([]))[0]
    assert "error" in run("plan_trip", None, FakeBackend([]))[0]


# ---------- LLM เรียก tools ----------

def call(cid, name, args):
    fn = type("F", (), {"name": name, "arguments": args})
    return type("T", (), {"id": cid, "type": "function", "function": fn})


def response(content=None, tool_calls=None):
    msg = type("M", (), {"content": content, "tool_calls": tool_calls})
    return type("R", (), {"choices": [type("C", (), {"message": msg})]})


def fake_llm(monkeypatch, script):
    """script[model] คือคำตอบตามลำดับ ถ้าเป็น Exception จะ raise"""
    monkeypatch.setenv("LLM_PRIMARY", "groq")
    monkeypatch.setenv("LLM_FALLBACK", "gemini")
    for p in ("GROQ", "GEMINI"):
        monkeypatch.setenv(f"{p}_API_KEY", "k")
        monkeypatch.setenv(f"{p}_MODEL", p.lower())
    sent = []

    class FakeClient:
        def __init__(self, **kw):
            self.chat = self.completions = self

        def create(self, model, messages, **kw):
            sent.append((model, [dict(m) for m in messages], kw))
            step = script[model].pop(0)
            if isinstance(step, Exception):
                raise step
            return step

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    return sent


def test_llm_moves_trip_through_tool_and_returns_action(monkeypatch):
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    sent = fake_llm(monkeypatch, {"groq": [
        response(tool_calls=[call("c1", "update_trip_time", '{"trip_no": 1, "shift_days": 1}')]),
        response(tool_calls=[call("c2", "plan_trip", '{"trip_no": 1}')]),
        response("เลื่อนให้แล้วครับ ความเสี่ยงต่ำ"),
    ]})
    out = llm.answer("ขอขยับทริปแรกไปอีกวันได้ไหม", [], [], lambda n, a: tools.run(n, a, be, AUTH))
    assert out["reply"] == "เลื่อนให้แล้วครับ ความเสี่ยงต่ำ" and out["warnings"] == []
    assert out["actions"] == [{"type": "TRIP_UPDATED", "trip_id": "id-1", "trip_no": 1}]
    assert be.patched() == [{"departure_time": "2030-01-06T01:00:00Z"}]
    assert sent[0][2]["tools"] == tools.SCHEMAS
    last = sent[-1][1]
    assert last[-1]["role"] == "tool" and last[-1]["tool_call_id"] == "c2"
    assert json.loads(last[-3]["content"])["updated"] is True


def test_no_fallback_restart_after_trip_was_changed(monkeypatch):
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    sent = fake_llm(monkeypatch, {
        "groq": [response(tool_calls=[call("c1", "update_trip_time", '{"trip_no": 1, "shift_days": 1}')]),
                 llm.OpenAIError("rate limited")],
        "gemini": [response("ไม่ควรถูกเรียก")],
    })
    out = llm.answer("เลื่อนทริปแรกไปอีกวัน", [], [], lambda n, a: tools.run(n, a, be, AUTH))
    assert [s[0] for s in sent] == ["groq", "groq"]
    assert len(be.patched()) == 1
    assert out["warnings"] == ["LLM_UNAVAILABLE"] and len(out["actions"]) == 1
    assert "เลื่อน Trip 01 ไปออกเดินทาง 6 ม.ค. 08:00 น. แล้ว" in out["reply"] and "ต่ำ" in out["reply"]


def test_failed_tool_gives_no_action_and_fallback_can_retry(monkeypatch):
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    fake_llm(monkeypatch, {
        "groq": [response(tool_calls=[call("c1", "update_trip_time", "{not json")]), llm.OpenAIError("down")],
        "gemini": [response("ขอเลขทริปด้วยครับ")],
    })
    out = llm.answer("เลื่อนหน่อย", [], [], lambda n, a: tools.run(n, a, be, AUTH))
    assert out == {"reply": "ขอเลขทริปด้วยครับ", "actions": [], "warnings": []}
    assert be.patched() == []


def test_tool_loop_stops_after_max_rounds(monkeypatch):
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    loop = [response(tool_calls=[call(f"c{i}", "list_trips", "{}")]) for i in range(llm.MAX_TOOL_ROUNDS + 1)]
    sent = fake_llm(monkeypatch, {"groq": loop, "gemini": [response("มี Trip 01 ครับ")]})
    out = llm.answer("มีทริปอะไรบ้าง", [], [], lambda n, a: tools.run(n, a, be, AUTH))
    assert sum(s[0] == "groq" for s in sent) == llm.MAX_TOOL_ROUNDS + 1
    assert out["reply"] == "มี Trip 01 ครับ"


def test_chat_endpoint_gives_llm_the_users_token(monkeypatch):
    be = FakeBackend([full_trip(1, "2030-01-05T01:00:00Z")])
    monkeypatch.setattr(agent, "backend", be)
    monkeypatch.setattr(agent, "safety_search", lambda q: [])
    fake_llm(monkeypatch, {"groq": [
        response(tool_calls=[call("c1", "update_trip_time", '{"trip_no": 1, "time": "17:00"}')]),
        response("ย้ายไปช่วงเย็นแล้วครับ"),
    ]})
    data = TestClient(agent.app).post("/api/v1/chat", headers={"Authorization": AUTH},
                                      json={"message": "ขอออกเดินทางตอนห้าโมงเย็นแทน"}).json()["data"]
    assert data["actions"] == [{"type": "TRIP_UPDATED", "trip_id": "id-1", "trip_no": 1}]
    assert be.patched() == [{"departure_time": "2030-01-05T10:00:00Z"}]
