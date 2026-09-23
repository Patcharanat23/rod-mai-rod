// ส่งต่อ /api/v1/* ไป api-backend ฝั่ง server อ่าน API_INTERNAL_URL ตอนรัน (ไม่ใช่ตอน build)
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function forward(req: NextRequest) {
  const base = process.env.API_INTERNAL_URL || "http://localhost:8001";
  const url = base + req.nextUrl.pathname + req.nextUrl.search;
  const headers: Record<string, string> = { "content-type": req.headers.get("content-type") || "application/json" };
  for (const h of ["authorization", "x-request-id"]) {
    const v = req.headers.get(h);
    if (v) headers[h] = v;
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
    const res = new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
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
