# apps/web - Frontend (โมดูล 1, 2, 3, 9 ทำในแอปเดียวกัน)

Next.js 15 (App Router) + TypeScript + Leaflet ดีไซน์ธีมกระจกเข้ม (Dark Glass) มาสคอตน้องกิเลน

```bash
cd apps/web
npm ci
cp .env.example .env.local   # ชี้ไป api-backend ที่ http://localhost:8001
npm run dev                  # http://localhost:3000
npm run typecheck            # ต้องผ่านก่อนเปิด PR
npm run build                # ต้องผ่านก่อนเปิด PR (Docker และ Render build แบบนี้)
```

บัญชีทดลอง `demo@example.com` / `demo1234` (api-backend สร้างให้ตอนเริ่ม) หรือสมัครใหม่จากหน้า login

## ใครดูแลไฟล์ไหน

| ไฟล์ | หน้า | โมดูล |
|---|---|---|
| `app/layout.tsx`, `app/globals.css`, `app/page.tsx`, `app/login/`, `components/{Shell,Icon,Map,MapView,ui,ChatFab,ChatDrawer}.tsx`, `lib/*`, `public/assets/`, `app/api/v1/`, `app/health/` | โครงเว็บ หน้าหลัก login แชทลอย ของกลาง | 1 |
| `app/trips/`, `components/PlanTrip.tsx`, `components/trip.tsx` | ทริปของฉัน + ฟอร์มวางแผน + เช็กลิสต์ + ออกเวลาไหนดี | 2 |
| `app/map/`, `app/assistant/` | แผนที่ความเสี่ยง + คุยกับน้องกิเลนเต็มหน้า | 3 |
| `app/emergency/` | ฉุกเฉิน (สมุดเบอร์ + วิธีรับมือ) | 9 |

หน้าตาต้องตรงกับภาพใน `public/assets/showcase/` (ถ่ายจากเว็บจริง) **ห้ามเปลี่ยนสี ขนาด หรือข้อความเอง** ถ้าจำเป็นต้องเปลี่ยนให้คุยกับเจ้าของโมดูล 1 ก่อน

## สิ่งที่เว็บต้องทำเสมอ (ห้ามพัง)

- `GET /health` ตอบ `{"status":"ok","service":"web"}` · ฟังพอร์ต 8000 ใน container (compose map ออกเป็น 3000)
- ส่งต่อ `/api/v1/*` ไปที่ `API_INTERNAL_URL` ด้วย `app/api/v1/[...path]/route.ts` ที่อ่าน env ตอนรัน ส่ง `Authorization`, `X-Request-ID`, **`X-Forwarded-For`** ต่อ (api-backend จำกัด login ต่อ IP ไม่ส่งต่อ = ทุกคนนับเป็น IP เดียว) ภาพชั้นน้ำท่วมส่งต่อเป็นไฟล์ภาพ
- **อย่าใช้ `rewrites` ใน `next.config`** ค่าในนั้นถูกฝังตอน build ใน Docker/Render จะชี้ผิดที่
- browser เรียก api-backend ผ่าน `api()` ใน `lib/api.ts` เท่านั้น (แนบ token, แกะ `{data, error}`, 401 พากลับหน้า login)

## ของกลาง (ใช้ตัวนี้ ห้ามเขียนซ้ำ)

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `lib/api.ts` | `api<T>(path, {method, body, timeoutMs, signal})` + `ApiError` (`code`, `message` ภาษาคน) |
| `lib/store.tsx` | `useApp()` ทริป หมุดภัย อากาศรอบตัว ตำแหน่ง แจ้งเตือน `floodWindow` + คำสั่งสร้าง/แก้/ลบ/วางแผนทริป `loadDepartures()` |
| `lib/chat.tsx` | บทสนทนากับน้องกิเลน (แชทลอยและหน้าเต็มใช้ชุดเดียวกัน) เก็บประวัติในเครื่องแยกตามบัญชี |
| `lib/data.ts` | ชนิดข้อมูลตาม CONTRACT, `RISK_TH`, `RISK_COLOR`, `RECO`, `HAZARD_META`, เวลาไทย (`thaiTime`, `thaiDateTime`, ...) |
| `lib/segments.ts` | ระบายสีเส้นทางตามความเสี่ยงแต่ละช่วง, ระยะทาง |
| `lib/theme.ts`, `lib/mapStyle.ts`, `lib/layout.tsx` | ธีม, สีแผนที่, ขนาดตัวอักษร + ลากปรับขนาดการ์ด (`useSplit`) |
| `components/Map.tsx` | แผนที่ Leaflet (ปิด SSR ให้แล้ว) หมุด กลุ่มหมุด เส้นทาง วงรัศมี ชั้นน้ำท่วม |
| `components/Shell.tsx` | `Topbar`, เมนูซ้ายพับได้, แถบล่างมือถือ, `openChat()` |
| `components/ui.tsx`, `components/Icon.tsx` | การ์ดหัวเรื่อง ป้ายความเสี่ยง และไอคอนทั้งเว็บ |

**ถ้าเปลี่ยน props ของของกลาง ต้องแจ้งเจ้าของโมดูล 2, 3, 9 ก่อน** ไม่งั้นหน้าเขาพังตอน merge

## จุดที่คนส่วนใหญ่พลาด

1. **ต่างคนต่างลง package** ขอเจ้าของโมดูล 1 ก่อน lockfile conflict ให้ลบแล้ว `npm install` ใหม่ ห้ามแก้ด้วยมือ
2. **เรียก `http://localhost:8001` ตรง** พังใน Docker/Render ให้เรียก `/api/v1/...` ผ่าน `lib/api.ts`
3. **Leaflet พังตอน build** ใช้ `components/Map` (dynamic ปิด SSR) อย่า import `MapView` ตรง
4. **แสดงเวลาตาม timezone เครื่อง** ใช้ตัวช่วยใน `lib/data.ts` (`Asia/Bangkok`) เสมอ
5. **ไม่มีสถานะโหลด/พัง/ว่าง** ทุกการ์ดและแผนที่ต้องมีครบ 3 สถานะ
6. **สีตายตัวในหน้า** ใช้ตัวแปรใน `globals.css` (`var(--lime)` ฯลฯ) ไม่งั้นธีมขาวใสพัง
