// หน้าเว็บชั่วคราว เจ้าของโมดูล 1 จะแทนที่ทั้งโฟลเดอร์นี้ด้วย Next.js
// สิ่งที่ Next.js ตัวจริงต้องทำเหมือนกัน:
//   - GET /health
//   - ฟังพอร์ต 8000 ภายใน container
//   - ส่งต่อ /api/v1/* ไปที่ API_INTERNAL_URL ฝั่ง server (browser ไม่ต้องรู้ที่อยู่ api-backend และไม่ติด CORS)
const express = require("express");

const app = express();
const PORT = process.env.PORT || 8000;
const API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://localhost:8001";

app.get("/health", (req, res) => res.json({ status: "ok", service: "web" }));

app.use("/api/v1", express.raw({ type: "*/*", limit: "1mb" }), async (req, res) => {
  const headers = { "content-type": req.get("content-type") || "application/json" };
  if (req.get("authorization")) headers.authorization = req.get("authorization");
  if (req.get("x-request-id")) headers["x-request-id"] = req.get("x-request-id");
  try {
    const upstream = await fetch(API_INTERNAL_URL + req.originalUrl, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) || !Buffer.isBuffer(req.body) ? undefined : req.body,
      // timeout ตาม CONTRACT หัวข้อ 3: แชทนานกว่าเส้นอื่น
      signal: AbortSignal.timeout(req.path.startsWith("/assistant/chat") ? 120000 : 60000),
    });
    const rid = upstream.headers.get("x-request-id");
    if (rid) res.set("X-Request-ID", rid);
    res.status(upstream.status).type("application/json").send(await upstream.text());
  } catch (err) {
    const timedOut = err.name === "TimeoutError";
    res.status(timedOut ? 504 : 502).json({
      data: null,
      error: { code: timedOut ? "UPSTREAM_TIMEOUT" : "UPSTREAM_ERROR", message: "ติดต่อ api-backend ไม่ได้" },
    });
  }
});

const page = (title, owner) =>
  `<!doctype html><meta charset="utf-8"><title>rod-mai-rod</title>` +
  `<nav><a href="/overview">Overview</a> | <a href="/my-trip">My Trip</a> | ` +
  `<a href="/safety-map">Safety Map</a> | <a href="/assistant">Assistant</a></nav>` +
  `<h1>${title}</h1><p>หน้าชั่วคราว เจ้าของ: ${owner}</p>`;

app.get("/", (req, res) => res.redirect("/login"));
app.get("/login", (req, res) => res.send(page("Login", "โมดูล 1")));
app.get("/overview", (req, res) => res.send(page("Overview", "โมดูล 1")));
app.get("/my-trip", (req, res) => res.send(page("My Trip", "โมดูล 2")));
app.get("/safety-map", (req, res) => res.send(page("Safety Map", "โมดูล 3")));
app.get("/assistant", (req, res) => res.send(page("Assistant", "โมดูล 3")));

app.listen(PORT, () => console.log(`web listening on ${PORT}, api -> ${API_INTERNAL_URL}`));
