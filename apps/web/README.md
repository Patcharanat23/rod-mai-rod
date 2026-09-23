# apps/web - Frontend (โมดูล 1, 2, 3 ทำในแอปเดียวกัน)

Next.js 15 (App Router) + TypeScript + Leaflet โครงเว็บ, `shared/`, login และ Overview เสร็จแล้ว
หน้า My Trip, Safety Map, Assistant มีเวอร์ชันพื้นฐานที่ใช้งานได้ จุดที่เจ้าของต้องเติมมี `TODO(<module-slug>)` กำกับ

```bash
cd apps/web
npm ci
cp .env.example .env.local   # ชี้ไป api-backend ที่ http://localhost:8001
npm run dev                  # http://localhost:3000
npm run typecheck            # ต้องผ่านก่อนเปิด PR
```

login ด้วยอีเมลอะไรก็ได้ รหัสผ่าน 6 ตัวขึ้นไป (api-backend ยังเป็น stub)

| โฟลเดอร์ | หน้า | โมดูล | branch |
|---|---|---|---|
| โครงเว็บ, `app/layout`, `shared/`, `app/login/`, `app/overview/` | Login + Overview | 1 | `feature/web-overview/<ชื่อ>` |
| `app/my-trip/` | My Trip | 2 | `feature/web-mytrip/<ชื่อ>` |
| `app/safety-map/`, `app/assistant/` | Safety Map + Assistant | 3 | `feature/web-safety-assistant/<ชื่อ>` |

## สิ่งที่เว็บต้องทำเสมอ (ทำไว้แล้ว ห้ามพัง)

- `GET /health` ตอบ `{"status":"ok","service":"web"}`
- ฟังพอร์ต 8000 ใน container (Dockerfile ใหม่ต้องตั้งแบบนี้ compose map ออกเป็น 3000)
- ส่งต่อ `/api/v1/*` ไปที่ `API_INTERNAL_URL` ฝั่ง server ด้วย route handler `app/api/v1/[...path]/route.ts` ที่อ่าน env ตอนรัน (ส่ง `Authorization` และ `X-Request-ID` ต่อ และส่ง `X-Request-ID` กลับ) browser เรียกแบบ relative path เท่านั้น
- **อย่าใช้ `rewrites` ใน `next.config`** ค่า env ในนั้นถูกฝังตอน build ตอนรันใน Docker จะชี้ไปผิดที่
- timeout ของการส่งต่อ: 60 วินาที ยกเว้น `/api/v1/assistant/chat` 120 วินาที

## ของกลางใน `shared/` (ใช้ตัวนี้ ห้ามเขียนซ้ำ)

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `api.ts` | `api<T>(path, {method, body})` เรียก api-backend แนบ token + `X-Request-ID` แกะ `{data, error}` เจอ 401 พากลับหน้า login |
| `useApi.ts` | `useApi<T>(path)` ดึงข้อมูลตอนเปิดหน้า ได้ `data, error, loading, reload` |
| `StatusBox.tsx` | สถานะ กำลังโหลด / พังพร้อมปุ่มลองใหม่ / ไม่มีข้อมูล |
| `Warnings.tsx` | แถบแจ้งเตือนจาก `warnings` เป็นภาษาไทย |
| `Map.tsx` | แผนที่ Leaflet (ปิด SSR ให้แล้ว) props: `center, zoom, routes, markers, fitTo, onBoundsChange, onMapClick` |
| `RiskBadge.tsx`, `risk.ts` | สีและป้ายระดับความเสี่ยง `null` แสดงเป็น "ไม่ทราบ" |
| `time.ts` | `formatThaiTime`, `formatDuration`, `thaiInputToUtc` (ค่าจาก datetime-local เป็น UTC), `utcToThaiInput` |
| `useLocation.ts` | ตำแหน่งผู้ใช้ ไม่อนุญาตหรือรอเกิน 5 วิ ใช้กรุงเทพ |
| `AreaWeather.tsx` | การ์ดแผนที่ + อากาศแบบ area ใช้ตอนไม่มีทริป |
| `types.ts` | ชนิดข้อมูลตาม CONTRACT |

**ถ้าเปลี่ยน props ของ component ใน `shared/` ต้องแจ้งเจ้าของโมดูล 2 และ 3 ก่อน** ไม่งั้นหน้าเขาพังตอน merge

## จุดที่คนส่วนใหญ่พลาด (ทุกคนที่ทำ frontend)

1. **ต่างคนต่างลง package** แล้ว lockfile ชนกัน ขอเจ้าของโมดูล 1 ก่อนเพิ่ม และถ้า lockfile conflict ให้ลบแล้ว `npm install` ใหม่บน branch ล่าสุด ห้ามแก้ lockfile ด้วยมือ
2. **เรียก api-backend ตรงด้วย `http://localhost:8001`** ใช้ได้บนเครื่องตัวเองแต่พังใน Docker และติด CORS ให้เรียก `/api/v1/...` ผ่าน `shared/api.ts` เท่านั้น
3. **Leaflet พังตอน build ของ Next.js** เพราะ Leaflet ใช้ `window` ต้อง import `MapView` แบบ dynamic ปิด SSR (`dynamic(() => import(...), { ssr: false })`)
4. **ส่งพิกัดให้ Leaflet ผิดลำดับ** Leaflet รับ `[lat, lng]` ส่วน GeoJSON เป็น `[lng, lat]` ระบบเราส่ง `{lat, lng}` แปลงใน `MapView` ที่เดียว
5. **แสดงเวลาตาม timezone ของเครื่อง** เครื่องที่ใช้สาธิตอาจตั้งเวลาไม่ใช่ไทย ใช้ `formatThaiTime()` เสมอ
6. **ไม่สนใจ `warnings`** ถ้ามี warning มาต้องมีแถบแจ้งผู้ใช้ เช่น "ข้อมูลสภาพอากาศบางส่วนไม่พร้อม"
7. **ไม่มีสถานะโหลด/พัง/ว่าง** ทุกการ์ดและแผนที่ต้องมีครบ 3 สถานะ ห้ามปล่อยหน้าขาว
8. **แสดงข้อความจาก error ของระบบแบบดิบ** ใช้ `error.message` (เขียนไว้เป็นภาษาคนแล้ว) ห้ามโชว์ stack trace หรือ JSON ทั้งก้อน
