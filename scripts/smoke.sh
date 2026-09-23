#!/bin/sh
# ไล่เส้นหลักของระบบผ่าน api-backend ใช้ได้ทั้งตอนเป็น stub และตอนเป็นของจริง
# ใช้: sh scripts/smoke.sh http://localhost:8001
BASE="${1:-http://localhost:8001}"
JSON='Content-Type: application/json'

fail() { echo "FAIL  $1"; echo "      $2"; exit 1; }
expect_ok() { echo "$2" | grep -q '"error":null' || fail "$1" "$2"; echo "ok    $1"; }
expect_code() { echo "$3" | grep -q "\"code\":\"$2\"" || fail "$1 (ต้องได้ $2)" "$3"; echo "ok    $1"; }
field() { echo "$1" | sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p"; }

R=$(curl -s --max-time 10 "$BASE/api/v1/trips")
expect_code "ไม่มี token ต้องโดนปฏิเสธ" UNAUTHORIZED "$R"

R=$(curl -s --max-time 10 -X POST "$BASE/api/v1/auth/login" -H "$JSON" \
  -d '{"email":"demo@example.com","password":"demo1234"}')
expect_ok "login" "$R"
TOKEN=$(field "$R" token)
[ -n "$TOKEN" ] || fail "login ไม่ได้ token กลับมา" "$R"
AUTH="Authorization: Bearer $TOKEN"

R=$(curl -s --max-time 10 -X POST "$BASE/api/v1/trips" -H "$AUTH" -H "$JSON" \
  -d '{"origin":{"lat":13.7563,"lng":100.5018,"name":"Bangkok"},"destination":{"lat":18.7883,"lng":98.9853,"name":"Chiang Mai"},"departure_time":"2030-01-01T01:00:00Z","waypoints":[{"lat":15.7047,"lng":100.1372,"name":"Nakhon Sawan"}]}')
expect_ok "สร้างทริป" "$R"
TRIP_ID=$(field "$R" trip_id)
[ -n "$TRIP_ID" ] || fail "สร้างทริปแล้วไม่ได้ trip_id" "$R"

R=$(curl -s --max-time 10 -X POST "$BASE/api/v1/trips" -H "$AUTH" -H "$JSON" \
  -d '{"origin":{"lat":35.68,"lng":139.76},"destination":{"lat":18.7883,"lng":98.9853},"departure_time":"2030-01-01T01:00:00Z"}')
expect_code "พิกัดนอกไทยต้องโดนปฏิเสธ" OUT_OF_THAILAND "$R"

R=$(curl -s --max-time 60 -X POST "$BASE/api/v1/trips/$TRIP_ID/plan" -H "$AUTH")
expect_ok "แพลนทริป" "$R"
echo "$R" | grep -q '"route_options":\[' || fail "แผนไม่มี route_options" "$R"
echo "$R" | grep -q '"is_recommended":true' || fail "ไม่มีเส้นทางที่ is_recommended" "$R"

R=$(curl -s --max-time 10 -X PATCH "$BASE/api/v1/trips/$TRIP_ID" -H "$AUTH" -H "$JSON" \
  -d '{"departure_time":"2030-01-02T06:00:00Z"}')
expect_ok "เลื่อนเวลาทริป" "$R"
echo "$R" | grep -q '"plan_status":"STALE"' || fail "แก้ทริปแล้วแผนเดิมต้องเป็น STALE" "$R"

R=$(curl -s --max-time 10 "$BASE/api/v1/trips/upcoming" -H "$AUTH")
expect_ok "ทริปถัดไป (Overview)" "$R"

R=$(curl -s --max-time 10 "$BASE/api/v1/weather/area?lat=13.75&lng=100.5" -H "$AUTH")
expect_ok "สภาพอากาศแบบพื้นที่" "$R"

R=$(curl -s --max-time 10 "$BASE/api/v1/hazards?min_lat=5.6&min_lng=97.3&max_lat=20.5&max_lng=105.7" -H "$AUTH")
expect_ok "หมุดภัย (Safety Map)" "$R"

R=$(curl -s --max-time 10 "$BASE/api/v1/safety/emergency?hazard_type=FLOOD" -H "$AUTH")
expect_ok "คำแนะนำฉุกเฉิน" "$R"

R=$(curl -s --max-time 120 -X POST "$BASE/api/v1/assistant/chat" -H "$AUTH" -H "$JSON" \
  -d '{"message":"เชียงใหม่ช่วงนี้น่าเที่ยวไหม","history":[]}')
expect_ok "แชท" "$R"
echo "$R" | grep -q '"actions":\[' || fail "คำตอบแชทต้องมี actions" "$R"

R=$(curl -s --max-time 10 -X DELETE "$BASE/api/v1/trips/$TRIP_ID" -H "$AUTH")
expect_ok "ลบทริป" "$R"

echo "ผ่านทุกข้อ"
