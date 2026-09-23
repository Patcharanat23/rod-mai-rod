# apps/web - Frontend (โมดูล 1, 2, 3 ทำในแอปเดียวกัน)

ตอนนี้เป็นเซิร์ฟเวอร์ Express ชั่วคราว (`server.js`) ที่มีหน้าเปล่า 5 หน้าและส่งต่อ `/api/v1/*` ไป api-backend ให้แล้ว
**เจ้าของโมดูล 1 เป็นคนสร้าง Next.js ตัวจริงแทนที่ทั้งโฟลเดอร์นี้ แล้ว merge เข้า `dev` ก่อนที่โมดูล 2 และ 3 จะเริ่มสร้างไฟล์ในนี้**
ระหว่างรอ โมดูล 2 และ 3 เขียน component ของหน้าตัวเองแยกไว้ก่อนได้ แล้วค่อยย้ายเข้ามาทีหลัง

| โฟลเดอร์ | หน้า | โมดูล | branch |
|---|---|---|---|
| โครงเว็บ, `app/layout`, `shared/`, `app/login/`, `app/overview/` | Login + Overview | 1 | `feature/web-overview/<ชื่อ>` |
| `app/my-trip/` | My Trip | 2 | `feature/web-mytrip/<ชื่อ>` |
| `app/safety-map/`, `app/assistant/` | Safety Map + Assistant | 3 | `feature/web-safety-assistant/<ชื่อ>` |

## สิ่งที่ Next.js ตัวจริงต้องทำเหมือน stub ตอนนี้

- `GET /health` ตอบ `{"status":"ok","service":"web"}`
- ฟังพอร์ต 8000 ใน container (Dockerfile ใหม่ต้องตั้งแบบนี้ compose map ออกเป็น 3000)
- ส่งต่อ `/api/v1/*` ไปที่ `API_INTERNAL_URL` ฝั่ง server ด้วย route handler `app/api/v1/[...path]/route.ts` ที่อ่าน env ตอนรัน (ส่ง `Authorization` และ `X-Request-ID` ต่อ และส่ง `X-Request-ID` กลับ) browser เรียกแบบ relative path เท่านั้น
- **อย่าใช้ `rewrites` ใน `next.config`** ค่า env ในนั้นถูกฝังตอน build ตอนรันใน Docker จะชี้ไปผิดที่
- timeout ของการส่งต่อ: 60 วินาที ยกเว้น `/api/v1/assistant/chat` 120 วินาที (ดู `server.js` ตอนนี้เป็นตัวอย่าง)

## ของกลางที่โมดูล 1 ต้องทำให้คนอื่นใช้ (ใน `shared/`)

- `api.ts` ตัวเรียก API กลาง: แนบ token, สร้าง `X-Request-ID`, แกะ `{data, error}`, เจอ 401 พาไปหน้า login
- `MapView` แผนที่ Leaflet ตัวเดียวของทั้งเว็บ รับ props: จุดกึ่งกลาง, ระดับซูม, เส้นทาง (array ของ `{lat, lng}`), หมุด
- `formatThaiTime()` แปลง UTC เป็นเวลาไทยด้วย `timeZone: "Asia/Bangkok"`
- `RiskBadge` แสดง LOW/MEDIUM/HIGH ด้วยสีเดียวกันทุกหน้า
- ชนิดข้อมูล (types) ตาม `docs/CONTRACT.md` หัวข้อ 4 และ 6

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
