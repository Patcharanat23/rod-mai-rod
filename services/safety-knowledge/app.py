"""safety-knowledge (stub)

ค้นคำแนะนำความปลอดภัยจากเอกสารใน knowledge/ และตอบคำแนะนำฉุกเฉินตามชนิดภัย
ตอนนี้ค้นแบบนับคำที่ตรงกันง่ายๆ และคำแนะนำฉุกเฉินมีแค่บางชนิดภัย ที่ต้องเติมดู TODO(safety-knowledge)
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from envelope import ApiError, ok, setup

app = FastAPI(title="safety-knowledge")
setup(app, "safety-knowledge")

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
HAZARD_TYPES = {"RAIN", "HEAVY_RAIN", "STRONG_WIND", "FLOOD", "LANDSLIDE_RISK", "STORM", "EARTHQUAKE"}

CONTACTS = [
    {"name_th": "สายด่วนนิรภัย ปภ.", "phone": "1784"},
    {"name_th": "เจ็บป่วยฉุกเฉิน", "phone": "1669"},
    {"name_th": "เหตุด่วนเหตุร้าย", "phone": "191"},
]

# TODO(safety-knowledge): ครบทุก hazard_type ใน CONTRACT และระบุแหล่งที่มาจริง
EMERGENCY = {
    "FLOOD": ["อย่าขับผ่านน้ำที่มองไม่เห็นผิวถนน", "ถ้ารถดับกลางน้ำ ออกจากรถไปที่สูงทันที", "ติดตามประกาศของ ปภ."],
    "HEAVY_RAIN": ["ลดความเร็วและเปิดไฟหน้า", "ถ้ามองไม่เห็นทาง จอดในที่ปลอดภัยรอให้ฝนเบาลง"],
}


class SearchIn(BaseModel):
    query: str
    hazard_types: list[str] = []
    limit: int = Field(3, ge=1, le=10)


def load_docs() -> list[dict]:
    """อ่านไฟล์ .md ใน knowledge/ ส่วนหัวระหว่าง --- คือ title_th, hazard_types, source"""
    docs = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        _, head, body = path.read_text(encoding="utf-8").split("---", 2)
        meta = dict(line.split(":", 1) for line in head.strip().splitlines())
        docs.append({
            "doc_id": path.stem,
            "title_th": meta["title_th"].strip(),
            "hazard_types": [h.strip() for h in meta.get("hazard_types", "").split(",") if h.strip()],
            "source": meta.get("source", "").strip(),
            "lines": [ln.strip() for ln in body.strip().splitlines() if ln.strip()],
        })
    return docs


DOCS = load_docs()


def score(query: str, line: str) -> int:
    # TODO(safety-knowledge): ภาษาไทยไม่มีเว้นวรรค นับทั้งคำแบบนี้แทบไม่เจอ ดู README ข้อ 1
    return sum(1 for word in query.split() if word and word in line)


@app.post("/api/v1/safety/search")
def search(body: SearchIn):
    if not body.query.strip():
        raise ApiError("VALIDATION_ERROR", "ข้อความค้นหาว่าง")
    wanted = set(body.hazard_types)
    hits = []
    for doc in DOCS:
        if wanted and not wanted & set(doc["hazard_types"]):
            continue
        for line in doc["lines"]:
            s = score(body.query, line) + (1 if wanted else 0)
            if s > 0:
                hits.append((s, {"doc_id": doc["doc_id"], "title_th": doc["title_th"],
                                 "snippet_th": line, "source": doc["source"]}))
    hits.sort(key=lambda h: -h[0])
    return ok({"results": [h[1] for h in hits[:body.limit]], "warnings": []})


@app.get("/api/v1/safety/emergency")
def emergency(hazard_type: str):
    if hazard_type not in HAZARD_TYPES:
        raise ApiError("VALIDATION_ERROR", f"ไม่รู้จัก hazard_type: {hazard_type}")
    steps: Optional[list[str]] = EMERGENCY.get(hazard_type)
    if steps is None:
        raise ApiError("NOT_FOUND", "ยังไม่มีคำแนะนำสำหรับภัยชนิดนี้")
    return ok({"hazard_type": hazard_type, "steps_th": steps, "contacts": CONTACTS})
