# MODULES.md - แบ่งงาน 8 คน 9 โมดูล

มีเวลา 5 วัน ดูว่าอะไรต้องมีและอะไรตัดได้ใน [`PLAN.md`](PLAN.md) ใครเสร็จก่อนไปช่วยงานอื่นหรือทำส่วนเสริมได้เลย
ทุกโมดูลมี stub ที่ตอบข้อมูลตัวอย่างตามรูปแบบจริงและเรียกหากันจริงแล้ว **ไม่มีใครต้องรอใครเพื่อเริ่มงาน** จุดที่ต้องเติมมี `TODO(<module-slug>)` กำกับไว้
README ในโฟลเดอร์ของแต่ละโมดูลมีรายการ "จุดที่คนส่วนใหญ่พลาด" อ่านก่อนเขียนบรรทัดแรก

## รายชื่อโมดูล

| # | โมดูล | โฟลเดอร์ | module-slug | การมอบหมาย |
|---|---|---|---|---|
| 1 | Frontend: โครงเว็บ + Login + Overview + ของกลาง `shared/` | `apps/web/` (โครง), `app/login/`, `app/overview/` | `web-overview` | เจ้าของโปรเจกต์ (เสร็จแล้ว ดูแลต่อ + รีวิวทุก PR) |
| 2 | Frontend: My Trip | `apps/web/app/my-trip/` | `web-mytrip` | TBD |
| 3 | Frontend: Safety Map + หน้าแชท | `apps/web/app/safety-map/`, `app/assistant/` | `web-safety-assistant` | TBD |
| 4 | API Gateway + Auth + ฐานข้อมูล | `services/api-backend/` | `api-backend` | **ล็อกให้พี่ที่เก่ง backend/API** |
| 5 | Routing Engine + เส้นทางสำรอง | `services/routing-engine/` | `routing-engine` | TBD |
| 6 | Weather & Disaster | `services/weather-disaster/` | `weather-disaster` | TBD |
| 7 | Risk & Decision | `services/risk-decision/` | `risk-decision` | TBD |
| 8 | Assistant Agent (แชท + สั่งแก้ทริป) | `services/assistant-agent/` | `assistant-agent` | TBD |
| 9 | Safety Knowledge (คำแนะนำความปลอดภัย + ฉุกเฉิน) | `services/safety-knowledge/` | `safety-knowledge` | TBD |

## อันดับความยาก (ใช้เลือกคน)

| อันดับ | โมดูล | ระดับ | ยากตรงไหน | เหมาะกับ |
|---|---|---|---|---|
| 1 | 8 assistant-agent | ยากมาก | LLM + function calling ต้องแก้ข้อมูลจริงให้ถูกทุกครั้ง, แปลง "พรุ่งนี้/ช่วงบ่าย" เป็นเวลาจริงตามเวลาไทย, ตัวแยกคำสั่งสำรองตอน LLM ล่ม | คนเก่งที่สุดในทีม หรือคนที่เคยใช้ LLM API |
| 2 | 5 routing-engine | ยาก | แกะผลจาก OSRM, เก็บจุดตัวอย่างทุก 20 กม. พร้อมเวลาถึงสะสม, ย่อเส้น, cache, fixture | คนเก่ง ชอบคิดเชิงอัลกอริทึม |
| 3 | 4 api-backend | ยาก | Postgres + bcrypt + JWT, ตรวจเจ้าของทริปทุกเส้น, endpoint เยอะ และเป็นจุดเดียวที่ห้ามล่ม | พี่ที่เก่ง backend (ล็อกไว้แล้ว) |
| 4 | 2 web-mytrip | กลางค่อนยาก | หน้าที่ซับซ้อนที่สุด ฟอร์ม + หลายเส้นทาง + popup + แท็บขวา + state หลายตัว | คนที่เขียน React ได้คล่องที่สุด |
| 5 | 6 weather-disaster | กลาง | เรียก Open-Meteo / GDACS / USGS, timezone, หน่วย, cache, แหล่งหนึ่งพังห้ามลากทั้งหมด | คนที่ละเอียด อ่านเอกสาร API เป็น |
| 6 | 7 risk-decision | กลาง | เกณฑ์หลักและเทสต์ทำไว้แล้ว เหลือหมุดภัยในรัศมี 20 กม., `risk_score`, `summary_th` และ `DELAY` ถ้าเหลือเวลา | คนที่ชอบตรรกะ เขียนเทสต์เป็น |
| 7 | 9 safety-knowledge | ค่อนง่าย | เขียนเอกสารความปลอดภัยพร้อมแหล่งที่มา + ทำให้ค้นภาษาไทยได้ (ไม่มีเว้นวรรค) | คนที่เขียนโค้ดยังไม่คล่อง แต่ค้นข้อมูลเก่งและละเอียด |
| 8 | 3 web-safety-assistant | ง่าย | สองหน้าใช้งานได้แล้วในระดับพื้นฐาน เหลือ debounce, ไอคอน, การ์ด actions, ปุ่มตัวอย่าง | คนที่เพิ่งเริ่มเขียน React |

โมดูล 8 กับ 5 ยากพอกันคนละแบบ ถ้าคนเก่งถนัด LLM ให้ถือ 8 ถ้าถนัดคิดเชิงอัลกอริทึมให้ถือ 5

## ใครรอใคร (สำหรับของจริง ตอนนี้ทุกคนต่อ stub ได้เลย)

```
weather-disaster ──> risk-decision ──> routing-engine ──> api-backend ──> frontend
                                                          api-backend <──> assistant-agent
safety-knowledge ──> assistant-agent, api-backend (คำแนะนำฉุกเฉิน)
```

**ลำดับแนะนำ**

1. โมดูล 4 ต่อ Postgres + auth จริง โดยยังตอบรูปแบบเดิม frontend จะไม่รู้สึกถึงการเปลี่ยน
2. โมดูล 6 ต่อ Open-Meteo จริงก่อนแหล่งอื่น เพราะ 7 และ 5 ต้องใช้
3. ที่เหลือทำพร้อมกันได้หมด

## ทางถอยถ้าไม่ทัน

ดู `docs/RUNBOOK.md` หัวข้อ E ทุกโมดูลมีเวอร์ชันเล็กที่ยังสาธิตได้ ตัดสินใจถอยให้เร็ว อย่ารอจนใกล้นำเสนอ
