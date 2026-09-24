"""ถามตอบทั่วไปผ่าน LLM ด้วยไลบรารี openai ตัวเดียว เปลี่ยนผู้ให้บริการด้วย base_url (CONTRACT หัวข้อ 10)"""
import json
import logging
import os
import re
import time
from typing import Callable, Optional

from openai import OpenAI, OpenAIError

import rules
import tools
from envelope import _request_id

log = logging.getLogger("assistant-agent")

LLM_TIMEOUT = 30  # วินาทีต่อครั้ง ตาม CONTRACT หัวข้อ 3
HISTORY_LIMIT = 10
MAX_TOOL_ROUNDS = 4
TIME_BUDGET = 90  # วินาที api-backend รอเรา 100 วิ
TOOL_MIN_TIME = 45  # ต้องเหลือเวลาพอให้ /plan ตอบ (api-backend รอ routing-engine 45 วิ)

RunTool = Callable[[str, Optional[dict]], tuple[dict, list]]

SYSTEM_PROMPT = (
    "คุณคือผู้ช่วยวางแผนเที่ยวในประเทศไทยของเว็บ rod-mai-rod "
    "ตอบสั้น กระชับ ไม่เกิน 5 บรรทัด เป็นภาษาเดียวกับที่ผู้ใช้พิมพ์ (ส่วนใหญ่คือภาษาไทย) ภาษาไทยลงท้ายด้วยครับ "
    "หน้าแชทแสดงข้อความธรรมดา ห้ามใช้ markdown เช่น ** หรือ # ใช้ขีด - นำหน้าข้อได้ "
    "บอกระดับความเสี่ยงเป็นคำไทย (ต่ำ ปานกลาง สูง) ห้ามพิมพ์รหัสภาษาอังกฤษของระบบ "
    "ห้ามแต่งข้อมูลสภาพอากาศ ความเสี่ยง หรือเบอร์โทรเอง ถ้าไม่มีข้อมูลให้บอกตรงๆ "
    "ระดับความเสี่ยงของทริปมาจากระบบเท่านั้น คุณไม่ได้เป็นคนตัดสิน "
    "ถ้าผู้ใช้สั่งดูหรือแก้ทริป ให้เรียก tools ที่มี ห้ามบอกว่าแก้แล้วถ้า tool ไม่ได้ตอบว่าสำเร็จ "
    "ถ้าไม่ชัดว่าหมายถึงทริปไหน ให้ถามกลับหรือเรียก list_trips ห้ามเดา "
    "บอกระดับความเสี่ยงและตัวเลขอากาศตามที่ tool ตอบเท่านั้น"
)

FALLBACK_REPLY = (
    "ตอนนี้ตอบคำถามทั่วไปไม่ได้ชั่วคราว แต่ยังสั่งได้ เช่น "
    "\"เลื่อน Trip 01 ไปวันถัดไป\", \"เลื่อน Trip 01 เป็นช่วงบ่าย\", \"Trip 01 อากาศเป็นยังไง\""
)


def providers() -> list[dict]:
    """ผู้ให้บริการตามลำดับ LLM_PRIMARY แล้ว LLM_FALLBACK ข้ามตัวที่ยังไม่ได้ใส่ key หรือชื่อโมเดล"""
    out = []
    for name in (os.getenv("LLM_PRIMARY", ""), os.getenv("LLM_FALLBACK", "")):
        prefix = name.strip().upper()
        if not prefix:
            continue
        key, model = os.getenv(f"{prefix}_API_KEY"), os.getenv(f"{prefix}_MODEL")
        if key and model:
            out.append({"name": name, "api_key": key, "model": model, "base_url": os.getenv(f"{prefix}_BASE_URL")})
    return out


def clean(snippet: str) -> str:
    """บรรทัดในเอกสารขึ้นต้นด้วย "- " อยู่แล้ว ตัดออกไม่ให้ขึ้น "- -" ซ้อน"""
    return snippet.lstrip("-*• ").strip()


def document_reply(sources: list[dict]) -> str:
    """ตอบจากเอกสารตรงๆ ตอน LLM ล่ม รวมบรรทัดของแหล่งเดียวกันแล้วบอกที่มาครั้งเดียว"""
    by_source: dict[str, list[str]] = {}
    for s in sources:
        by_source.setdefault(s["source"], []).append(clean(s["snippet_th"]))
    parts = ["\n".join(f"- {line}" for line in lines) + f"\n(ที่มา: {src})" for src, lines in by_source.items()]
    return "ข้อแนะนำจากเอกสาร:\n" + "\n\n".join(parts)


def build_messages(message: str, history: list[dict], sources: list[dict]) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if sources:
        refs = "\n".join(f"- {clean(s['snippet_th'])} (ที่มา: {s['source']})" for s in sources)
        msgs.append({"role": "system", "content": "ข้อมูลความปลอดภัยจากเอกสารที่เชื่อถือได้ ใช้ตอบและบอกที่มา:\n" + refs})
    for h in history[-HISTORY_LIMIT:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": message})
    return msgs


def plain(text: str) -> str:
    """หน้าแชทแสดงข้อความธรรมดา โมเดลบางตัวยังใส่ markdown มาแม้สั่งห้าม ตัดทิ้งก่อนส่ง"""
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE).strip()


def tool_call_message(msg) -> dict:
    return {"role": "assistant", "content": msg.content or "", "tool_calls": [
        {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
        for c in msg.tool_calls]}


def done_reply(results: list[dict]) -> str:
    """ใช้ตอนแก้ทริปสำเร็จแล้วแต่ LLM ไม่ได้ตอบต่อ ต้องบอกผู้ใช้ว่าเกิดอะไรขึ้นจริง"""
    lines = []
    for r in results:
        if r.get("updated"):
            lines.append(f"เลื่อน {r['name']} ไปออกเดินทาง {r['departure_th']} แล้ว")
        elif r.get("planned"):
            lines.append(f"วางแผน {r['name']} ใหม่แล้ว")
        plan = r.get("plan") or (r if r.get("planned") else None)
        if plan:
            lines.append(f"ความเสี่ยงระดับ{plan.get('risk_th', 'ไม่ทราบ')} {plan.get('summary_th') or ''}".strip())
        if r.get("plan_error"):
            lines.append("แต่คำนวณเส้นทางใหม่ไม่สำเร็จ กด Plan ในหน้า My Trip อีกครั้งนะครับ")
    return "\n".join(lines)


def log_event(level: int, event: str, **fields):
    log.log(level, json.dumps({"service": "assistant-agent", "request_id": _request_id.get(),
                               "event": event, **fields}, ensure_ascii=False))


def unique(actions: list[dict]) -> list[dict]:
    """เลื่อนแล้วแพลนทริปเดียวกันซ้ำ ให้เหลือ action เดียว"""
    seen, out = set(), []
    for a in actions:
        key = (a["type"], a["trip_id"])
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def complete(messages: list[dict], run_tool: Optional[RunTool] = None) -> tuple[Optional[str], list, list]:
    """ลองตัวหลักก่อน ล่ม / 429 / โมเดลถูกถอด ค่อยลองตัวสำรอง
    คืน (ข้อความ หรือ None ถ้าล่มหมด, actions, ผลของ tools ที่แก้ข้อมูลสำเร็จ)"""
    deadline = time.monotonic() + TIME_BUDGET
    actions: list = []
    changed: list[dict] = []
    for p in providers():
        convo = list(messages)
        try:
            client = OpenAI(api_key=p["api_key"], base_url=p["base_url"], timeout=LLM_TIMEOUT, max_retries=0)
            extra = {"tools": tools.SCHEMAS} if run_tool else {}
            for _ in range(MAX_TOOL_ROUNDS + 1):
                remaining = deadline - time.monotonic()
                if remaining < 5:
                    break
                res = client.chat.completions.create(model=p["model"], messages=convo, temperature=0.3,
                                                     timeout=min(LLM_TIMEOUT, remaining), **extra)
                msg = res.choices[0].message
                if not getattr(msg, "tool_calls", None):
                    text = plain(msg.content or "")
                    if text:
                        return text, unique(actions), changed
                    break
                convo.append(tool_call_message(msg))
                for c in msg.tool_calls:
                    if deadline - time.monotonic() < TOOL_MIN_TIME:
                        result, acts = {"error": "หมดเวลา ให้ผู้ใช้ลองใหม่อีกครั้ง"}, []
                    else:
                        try:
                            args = json.loads(c.function.arguments or "{}")
                        except ValueError:
                            args = None
                        result, acts = run_tool(c.function.name, args)
                    log_event(logging.INFO, "tool_called", provider=p["name"], tool=c.function.name,
                              ok="error" not in result)
                    if acts:
                        actions += acts
                        changed.append(result)
                    convo.append({"role": "tool", "tool_call_id": c.id,
                                  "content": json.dumps(result, ensure_ascii=False)})
        except OpenAIError as e:
            log_event(logging.WARNING, "llm_failed", provider=p["name"], error=type(e).__name__)
        if actions:
            # แก้ทริปไปแล้ว ห้ามเริ่มใหม่กับตัวสำรอง ไม่งั้นจะเลื่อนซ้ำ
            break
    return None, unique(actions), changed


def answer(message: str, history: list[dict], sources: list[dict], run_tool: Optional[RunTool] = None) -> dict:
    text, actions, changed = complete(build_messages(message, history, sources), run_tool)
    if text is not None:
        return {"reply": text, "actions": actions, "warnings": []}
    if changed:
        return {"reply": done_reply(changed), "actions": actions, "warnings": ["LLM_UNAVAILABLE"]}
    # คำสั่งเกี่ยวกับทริป เช่น "ทริป 1 ออกเร็วขึ้น" ค้นเอกสารเจอ "ความเร็ว" ได้ ตอบจากเอกสารจะไม่ตรงคำถาม
    # ให้บอกคำสั่งที่ยังใช้ได้แทน
    if sources and not (rules.MOVE.search(message) or rules.TRIP_NO.search(message)):
        # LLM ล่มแต่มีข้อมูลจากเอกสาร ยังตอบจากเอกสารตรงๆ ได้
        return {"reply": document_reply(sources), "actions": [], "warnings": ["LLM_UNAVAILABLE"]}
    return {"reply": FALLBACK_REPLY, "actions": [], "warnings": ["LLM_UNAVAILABLE"]}
