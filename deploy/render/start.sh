#!/bin/bash
# เปิดบริการ Python 6 ตัวบน localhost แล้วเปิดหน้าเว็บที่พอร์ต $PORT
# ถ้าตัวไหนล้ม ให้ทั้ง container ล้ม Render จะเปิดใหม่ให้เอง (ดีกว่าค้างครึ่งๆ กลางๆ)
set -e
cd /app

# ที่อยู่ภายในระหว่างบริการ (ทับค่าใน .env ของ docker compose)
export API_BACKEND_URL=http://127.0.0.1:8001
export ROUTING_ENGINE_URL=http://127.0.0.1:8002
export WEATHER_DISASTER_URL=http://127.0.0.1:8003
export RISK_DECISION_URL=http://127.0.0.1:8004
export ASSISTANT_AGENT_URL=http://127.0.0.1:8005
export SAFETY_KNOWLEDGE_URL=http://127.0.0.1:8006
export API_INTERNAL_URL=http://127.0.0.1:8001

start() {  # start <ชื่อบริการ> <พอร์ต>
  SERVICE_NAME="$1" uvicorn app:app --app-dir "services/$1" --host 127.0.0.1 --port "$2" --log-level warning &
}
start api-backend 8001
start routing-engine 8002
start weather-disaster 8003
start risk-decision 8004
start assistant-agent 8005
start safety-knowledge 8006

# หน้าเว็บรอให้ api-backend พร้อมก่อน (ต่อฐานข้อมูลและสร้างตารางตอนเริ่ม)
i=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)" 2>/dev/null; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "api-backend ไม่พร้อมใน 60 วินาที"; exit 1; }
  sleep 1
done

cd web && PORT="${PORT:-10000}" HOSTNAME=0.0.0.0 node server.js &

# ตัวไหนจบ (ล้ม) ก็ปิดทั้ง container ให้ Render เปิดใหม่
wait -n
echo "มีบริการหยุดทำงาน ปิด container"
exit 1
