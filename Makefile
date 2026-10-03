.PHONY: up down reset logs ps health smoke

# สร้าง .env จากตัวอย่างให้อัตโนมัติถ้ายังไม่มี (กัน docker compose ล้มตั้งแต่เริ่ม)
.env:
	cp .env.example .env

up: .env
	docker compose up --build -d
	@echo "เปิดเว็บที่ http://localhost:3000  เช็คสถานะด้วย make health"

# หยุดทุกอย่าง แต่ข้อมูลในฐานข้อมูลยังอยู่
down:
	docker compose down

# ลบทุกอย่างรวมข้อมูลในฐานข้อมูล ใช้เมื่อ schema เปลี่ยนหรือข้อมูลเละเท่านั้น
reset:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

health:
	@for p in 3000 8001 8002 8003 8004 8005 8006; do \
		printf "port $$p  "; \
		curl -s --max-time 3 http://localhost:$$p/health || printf "FAILED"; \
		echo ""; \
	done

# ไล่เส้นหลักของระบบผ่าน api-backend: login, สร้างทริป, แพลน ต้องผ่านก่อน merge dev เข้า main
smoke:
	@sh scripts/smoke.sh http://localhost:8001
