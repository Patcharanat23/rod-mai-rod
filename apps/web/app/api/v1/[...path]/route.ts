// ส่งต่อ /api/v1/* ไป api-backend ฝั่ง server อ่าน API_INTERNAL_URL ตอนรัน (ไม่ใช่ตอน build)
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function forward(req: NextRequest) {
  const base = process.env.API_INTERNAL_URL;
  if (!base) {
    return Response.json(
      { data: null, error: { code: "INTERNAL_ERROR", message: "ยังไม่ได้ตั้งค่า API_INTERNAL_URL" } },
      { status: 500 },
    );
  }
  const url = base + req.nextUrl.pathname + req.nextUrl.search;
  const headers: Record<string, string> = { "content-type": req.headers.get("content-type") || "application/json" };
  for (const h of ["authorization", "x-request-id", "x-forwarded-for"]) {
    const v = req.headers.get(h);
    if (v) headers[h] = v;
  }
  // api-backend จำกัดจำนวนครั้ง login ต่อ IP ต้องส่ง IP ผู้ใช้จริงไป ไม่งั้นทุกคนนับเป็น IP ของ web
  if (!headers["x-forwarded-for"]) {
    const ip = req.headers.get("x-real-ip");
    if (ip) headers["x-forwarded-for"] = ip;
  }
  const timeoutMs = req.nextUrl.pathname.startsWith("/api/v1/assistant/chat") ? 120_000 : 60_000;

  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
    // ภาพแผนที่ (เช่น ชั้นน้ำท่วมจากดาวเทียม) ส่งต่อเป็นไฟล์ ไม่ใช่ข้อความ
    const type = upstream.headers.get("content-type") || "application/json";
    const binary = type.startsWith("image/");
    const res = new Response(binary ? await upstream.arrayBuffer() : await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": binary ? type : "application/json" },
    });
    if (binary) res.headers.set("cache-control", upstream.headers.get("cache-control") || "public, max-age=1800");
    const rid = upstream.headers.get("x-request-id");
    if (rid) res.headers.set("X-Request-ID", rid);
    return res;
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "TimeoutError";
    return Response.json(
      {
        data: null,
        error: { code: timedOut ? "UPSTREAM_TIMEOUT" : "UPSTREAM_ERROR", message: "ติดต่อระบบหลังบ้านไม่ได้ ลองใหม่อีกครั้ง" },
      },
      { status: timedOut ? 504 : 502 },
    );
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as PUT, forward as DELETE };
