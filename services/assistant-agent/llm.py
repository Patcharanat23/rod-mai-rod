"""ถามตอบทั่วไปผ่าน LLM ด้วยไลบรารี openai ตัวเดียว เปลี่ยนผู้ให้บริการด้วย base_url (CONTRACT หัวข้อ 10)"""
import json
import logging
import os
from typing import Optional

from openai import OpenAI, OpenAIError

from envelope import _request_id

log = logging.getLogger("assistant-agent")

LLM_TIMEOUT = 30  # วินาทีต่อครั้ง ตาม CONTRACT หัวข้อ 3
HISTORY_LIMIT = 10

SYSTEM_PROMPT = (
    "คุณคือผู้ช่วยวางแผนเที่ยวในประเทศไทยของเว็บ rod-mai-rod "
    "ตอบสั้น กระชับ เป็นภาษาเดียวกับที่ผู้ใช้พิมพ์ (ส่วนใหญ่คือภาษาไทย) "
    "ห้ามแต่งข้อมูลสภาพอากาศ ความเสี่ยง หรือเบอร์โทรเอง ถ้าไม่มีข้อมูลให้บอกตรงๆ "
    "ระดับความเสี่ยงของทริปมาจากระบบเท่านั้น คุณไม่ได้เป็นคนตัดสิน "
    "ถ้าผู้ใช้อยากเลื่อนทริป แนะนำให้พิมพ์แบบนี้: \"เลื่อน Trip 01 ไปวันถัดไป\", "
    "\"เลื่อน Trip 01 เป็นช่วงบ่าย\", \"Trip 01 อากาศเป็นยังไง\""
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


def complete(messages: list[dict]) -> Optional[str]:
    """ลองตัวหลักก่อน ล่ม / 429 / โมเดลถูกถอด ค่อยลองตัวสำรอง ล่มหมดคืน None"""
    for p in providers():
        try:
            client = OpenAI(api_key=p["api_key"], base_url=p["base_url"], timeout=LLM_TIMEOUT, max_retries=0)
            res = client.chat.completions.create(model=p["model"], messages=messages, temperature=0.3)
            text = (res.choices[0].message.content or "").strip()
            if text:
                return text
        except OpenAIError as e:
            log.warning(json.dumps({"service": "assistant-agent", "request_id": _request_id.get(),
                                    "event": "llm_failed", "provider": p["name"], "error": type(e).__name__}))
    return None


def answer(message: str, history: list[dict], sources: list[dict]) -> dict:
    text = complete(build_messages(message, history, sources))
    if text is None:
        if sources:
            # LLM ล่มแต่มีข้อมูลจากเอกสาร ยังตอบจากเอกสารตรงๆ ได้
            return {"reply": document_reply(sources), "actions": [], "warnings": ["LLM_UNAVAILABLE"]}
        return {"reply": FALLBACK_REPLY, "actions": [], "warnings": ["LLM_UNAVAILABLE"]}
    return {"reply": text, "actions": [], "warnings": []}
