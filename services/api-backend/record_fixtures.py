"""บันทึกคำตอบจริงของ Photon และ Overpass สำหรับ DEMO_MODE ต้องมีเน็ต

รันในโฟลเดอร์ services/api-backend: python record_fixtures.py
แล้วเปิดดูไฟล์ใน fixtures/ ก่อน commit
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import places
from envelope import ApiError
from geo import to_iso

# คำในเส้นสาธิต หน้าเว็บค้นทุกครั้งที่หยุดพิมพ์ จึงบันทึกทุกช่วงที่พิมพ์ไปทีละตัว
SEARCH_WORDS = ["กทม", "กรุงเทพ", "เชียงใหม่", "นครสวรรค์"]
# กรุงเทพ นครสวรรค์ เชียงใหม่ ชุดเดียวกับ weather-disaster
CITIES = [(13.756, 100.502), (15.705, 100.137), (18.788, 98.985)]
PAUSE_S = 1  # เว้นระหว่างคำขอ เซิร์ฟเวอร์ฟรีไม่ควรถูกยิงรัว
OVERPASS_TRIES = 3
OVERPASS_RETRY_WAIT_S = 30


def prefixes(word: str) -> list[str]:
    return [word[:i] for i in range(places.MIN_CHARS, len(word) + 1)]


def record_nearby(cell: tuple[float, float]) -> list[dict]:
    for attempt in range(1, OVERPASS_TRIES + 1):
        try:
            return places.fetch_nearby(*cell)
        except ApiError as e:
            print(f"  Overpass พัง ({e.code}) ครั้งที่ {attempt} รอ {OVERPASS_RETRY_WAIT_S} วิแล้วลองใหม่")
            time.sleep(OVERPASS_RETRY_WAIT_S)
    raise SystemExit(f"บันทึกช่อง {cell} ไม่ได้ ลองรันใหม่ภายหลัง")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: {path.stat().st_size // 1024} KB")


def main() -> None:
    places.FIXTURES.mkdir(exist_ok=True)
    recorded_at = to_iso(datetime.now(timezone.utc))

    # ของที่บันทึกไว้แล้วไม่ยิงซ้ำ รันใหม่หลังพังจะทำต่อเฉพาะที่ขาด
    queries = places._fixture(places.SEARCH_FIXTURE, "queries")
    for q in dict.fromkeys(p for word in SEARCH_WORDS for p in prefixes(word)):
        key = places.expand(q).lower()
        if key not in queries:
            queries[key] = places.fetch_search(places.expand(q))
            print(f"search {q}: {len(queries[key])} places")
            time.sleep(PAUSE_S)
    write_json(places.SEARCH_FIXTURE, {"recorded_at": recorded_at, "queries": queries})

    cells = places._fixture(places.NEARBY_FIXTURE, "cells")
    for lat, lng in CITIES:
        cell = (round(lat, 2), round(lng, 2))
        name = f"{cell[0]:.2f}_{cell[1]:.2f}"
        if name in cells:
            print(f"nearby {cell}: บันทึกไว้แล้ว ข้าม")
            continue
        found = record_nearby(cell)
        cells[name] = found
        # เขียนทุกช่องที่ได้ ถ้าช่องถัดไปพัง ของที่ได้แล้วไม่หาย
        write_json(places.NEARBY_FIXTURE, {"recorded_at": recorded_at, "cells": cells})
        print(f"nearby {cell}: {len(found)} places")
        time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()