# ตั้งค่า Discord สำหรับอัปเดตงาน (PR + แจกงาน + แจ้งผลรีวิว)

เป้าหมาย 3 อย่าง:
1. ห้อง **#pr-updates** - เห็นทุกครั้งที่มีใครเปิด/ปิด/merge PR (อัตโนมัติ ไม่ต้องเขียนโค้ด)
2. ห้อง **#task-assignment** - ไว้แจกงานให้แต่ละคน (ห้องธรรมดา ใช้มือโพสต์)
3. ห้องส่วนตัวของแต่ละโมดูล - บอทแจ้งอัตโนมัติเมื่อ PR ของโมดูลนั้นถูกรีวิวเสร็จ

ไม่ต้องสร้าง Discord bot เอง ใช้ **Incoming Webhook** + **GitHub Actions** (มีให้แล้วที่ `.github/workflows/pr-review-notify.yml`)

## ขั้นที่ 1 - สร้างห้อง

สร้างห้องตามนี้ (ตั้งชื่อห้องให้ตรงกับ module-slug จะได้ไม่งง):
- `#pr-updates`, `#task-assignment` (ทุกคนเห็น)
- `#pr-web-overview`, `#pr-web-mytrip`, `#pr-web-safety-assistant`
- `#pr-api-backend`, `#pr-routing-engine`, `#pr-weather-disaster`, `#pr-risk-decision`, `#pr-assistant-agent`

## ขั้นที่ 2 - ต่อ `#pr-updates` กับ GitHub (ไม่ต้องเขียนโค้ด)

1. ในห้อง `#pr-updates` → Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL
2. เติม `/github` ต่อท้าย URL
3. GitHub repo → Settings → Webhooks → Add webhook → Payload URL = URL ที่เติม `/github` แล้ว, Content type = `application/json`, Events = เลือกแค่ **Pull requests**

## ขั้นที่ 3 - ห้องส่วนตัวแต่ละโมดูลแจ้งผลรีวิวอัตโนมัติ

ทำซ้ำ 8 รอบ (หนึ่งรอบต่อหนึ่งโมดูล):

1. เข้าห้องโมดูลนั้น → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL (**ไม่ต้อง** เติม `/github`)
2. GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `DISCORD_WEBHOOK_<MODULE_SLUG ตัวพิมพ์ใหญ่ ขีดกลางเป็นขีดล่าง>` เช่น
     - `routing-engine` → `DISCORD_WEBHOOK_ROUTING_ENGINE`
     - `api-backend` → `DISCORD_WEBHOOK_API_BACKEND`
     - `web-mytrip` → `DISCORD_WEBHOOK_WEB_MYTRIP`
   - Secret: วาง URL ที่ copy มา

**สำคัญ**: ทุกคนต้องตั้งชื่อ branch เป็น `feature/<module-slug>/<ชื่อคุณ>` ตาม `docs/CONTRACT.md` เป๊ะ
เช่น `feature/routing-engine/somchai` - workflow อ่าน slug จากตำแหน่งที่ 2 ของชื่อ branch ถ้าตั้งผิดรูปแบบจะข้ามการแจ้งเตือน (เช็ค log ได้ที่แท็บ Actions)

## ขั้นที่ 4 - `#task-assignment`

ห้องธรรมดา ไม่ต้องต่อบอท ใช้ Pin ข้อความสรุปว่าใครรับโมดูลไหน (อัปเดตตารางใน README.md หลักด้วยทุกครั้งที่เปลี่ยน)

## เช็คว่าใช้งานได้จริง

เปิด PR ทดสอบ → เห็นใน `#pr-updates` → กด Approve/Request changes → ต้องเห็นข้อความเด้งเข้าห้องโมดูลนั้นภายในไม่กี่วินาที (เช็คแท็บ Actions ถ้าไม่เด้ง)
