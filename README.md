# rod-mai-rod

เว็บวางแผนการท่องเที่ยวที่ใช้ AI ร่วมกับข้อมูลสภาพอากาศและภัยธรรมชาติ ช่วยผู้ใช้ตัดสินใจว่าทริปไหนปลอดภัย ควรออกเมื่อไหร่ และควรไปทางไหน (ขอบเขตแรก: ประเทศไทย)

## อ่านตามลำดับนี้ก่อนเริ่มเขียนโค้ด

1. [`docs/SPEC.md`](docs/SPEC.md) ระบบต้องทำอะไรได้บ้าง
2. [`docs/CONTRACT.md`](docs/CONTRACT.md) กฎกลาง พอร์ต รูปแบบข้อมูล endpoint และ git flow **สำคัญที่สุด**
3. [`docs/MODULES.md`](docs/MODULES.md) ใครทำโมดูลไหน และใครรอใคร และ [`docs/PLAN.md`](docs/PLAN.md) แผน 5 วัน
4. README ในโฟลเดอร์โมดูลของตัวเอง มีรายการจุดที่คนมักพลาดเขียนดักไว้แล้ว
5. [`docs/RUNBOOK.md`](docs/RUNBOOK.md) ถ้าอะไรพังให้เปิดไฟล์นี้

## เริ่มต้นใช้งาน

```bash
make up        # สร้าง .env ให้ถ้ายังไม่มี แล้วรันทั้งระบบ
make health    # ทุก service ต้องตอบ ok
make smoke     # ไล่เส้นหลัก login > สร้างทริป > แพลน > แชท ต้องผ่านทุกข้อ
```

เปิดเว็บที่ http://localhost:3000

**ใครใช้ Windows และไม่มี `make`** ใช้คำสั่งเทียบนี้แทน:

| make | คำสั่งที่ใช้แทน |
|---|---|
| `make up` | `copy .env.example .env` (ครั้งแรกครั้งเดียว) แล้ว `docker compose up --build -d` |
| `make down` | `docker compose down` |
| `make reset` | `docker compose down -v` (ลบข้อมูลในฐานข้อมูลด้วย) |
| `make logs` | `docker compose logs -f --tail=100` |
| `make health` | `curl http://localhost:8001/health` (เปลี่ยนพอร์ตเป็น 3000, 8002 ถึง 8006 ทีละตัว) |
| `make smoke` | รัน `scripts/smoke.sh` ผ่าน Git Bash: `sh scripts/smoke.sh http://localhost:8001` |

ทุก service ตอนนี้เป็นตัวชั่วคราว (stub) ที่ตอบข้อมูลตัวอย่างตามรูปแบบจริงและส่งต่อกันจริงแล้ว ทุกคนต่อกันได้ทันทีโดยไม่ต้องรอใคร

ทดสอบโมดูลตัวเอง: `cd services/<โมดูล> && pip install -r requirements.txt pytest && pytest`

## โมดูล

| # | โมดูล | โฟลเดอร์ | พอร์ตบนเครื่อง | ผู้รับผิดชอบ |
|---|---|---|---|---|
| 1 | Frontend: โครงเว็บ + Login + Overview | `apps/web/app/overview/` | 3000 | เจ้าของโปรเจกต์ |
| 2 | Frontend: My Trip | `apps/web/app/my-trip/` | 3000 | TBD |
| 3 | Frontend: Safety Map + หน้าแชท | `apps/web/app/safety-map/`, `apps/web/app/assistant/` | 3000 | TBD |
| 4 | API Gateway + Auth + ฐานข้อมูล | `services/api-backend/` | 8001 | TBD |
| 5 | Routing Engine | `services/routing-engine/` | 8002 | TBD |
| 6 | Weather & Disaster | `services/weather-disaster/` | 8003 | TBD |
| 7 | Risk & Decision | `services/risk-decision/` | 8004 | TBD |
| 8 | Assistant Agent | `services/assistant-agent/` | 8005 | TBD |
| 9 | Safety Knowledge (คำแนะนำความปลอดภัย + ฉุกเฉิน) | `services/safety-knowledge/` | 8006 | TBD |

## Git flow สรุปสั้น

`feature/<module-slug>/<ชื่อ>` ไป `dev` (1 approval) ไป `main` (2 approval) ห้าม push ตรงเข้า `dev` หรือ `main`
แตะไฟล์นอกโฟลเดอร์ตัวเองต้องถามเจ้าของก่อน รายละเอียดอยู่ใน `docs/CONTRACT.md` หัวข้อ 11

## ระบบแจ้งเตือน

ตั้งค่า Discord ตาม [`docs/DISCORD_SETUP.md`](docs/DISCORD_SETUP.md)
