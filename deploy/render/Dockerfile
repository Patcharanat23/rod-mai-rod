# รอดไม่รอดทั้งระบบใน container เดียวสำหรับ Render (web service 1 ตัว)
# บริการ Python 6 ตัวฟังแค่ 127.0.0.1:8001-8006 หน้าเว็บ Next ฟังพอร์ต $PORT ที่ Render กำหนด
# build จาก root ของ repo: docker build -f deploy/render/Dockerfile .

# 1) build หน้าเว็บแบบ standalone
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

# 2) ตัวรัน: Python 3.12 + node (เอาแค่ไฟล์ node ไม่ต้องลง npm)
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 NODE_ENV=production
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
# ทุกบริการใช้ไลบรารีรุ่นเดียวกัน ลงรวมชุดเดียว
COPY services/api-backend/requirements.txt /tmp/req-api.txt
COPY services/assistant-agent/requirements.txt /tmp/req-agent.txt
RUN pip install --no-cache-dir -r /tmp/req-api.txt -r /tmp/req-agent.txt
COPY services/ ./services/
COPY --from=web /web/.next/standalone ./web/
COPY --from=web /web/.next/static ./web/.next/static
COPY --from=web /web/public ./web/public
COPY deploy/render/start.sh ./start.sh
RUN chmod +x start.sh
CMD ["./start.sh"]
