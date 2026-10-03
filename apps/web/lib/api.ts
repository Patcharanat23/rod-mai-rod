// เรียก api-backend ของระบบจริง (next.config.mjs ส่งต่อ /api/v1/* ไปที่ 127.0.0.1:8001)
// แนบ token, แกะ {data, error} ตาม docs/CONTRACT.md, เจอ 401 พากลับหน้า login
const TOKEN_KEY = "rmr_redesign_token";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

// timeoutMs: รอนานเกินนี้ยกเลิกเอง (กันหน้าค้าง) · signal: ให้ผู้ใช้กดยกเลิกเองได้
export async function api<T>(path: string, opts: { method?: string; body?: unknown; timeoutMs?: number; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    const signals = [opts.signal, opts.timeoutMs ? AbortSignal.timeout(opts.timeoutMs) : undefined].filter((x): x is AbortSignal => !!x);
    res = await fetch(`/api/v1${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: signals.length ? AbortSignal.any(signals) : undefined,
    });
  } catch (e) {
    if (opts.signal?.aborted) throw new ApiError("CANCELLED", "ยกเลิกแล้ว", 0);
    if ((e as Error).name === "TimeoutError") throw new ApiError("TIMEOUT", "ตอบช้าเกินไป ลองใหม่อีกครั้ง", 0);
    throw new ApiError("NETWORK", "เชื่อมต่อระบบไม่ได้ ลองใหม่อีกครั้ง", 0);
  }
  let json: { data: T; error: { code: string; message: string } | null } | null = null;
  try {
    json = await res.json();
  } catch {}
  if (res.status === 401 && !path.startsWith("/auth/")) {
    setToken(null);
    if (!location.pathname.startsWith("/login")) location.href = "/login";
  }
  if (!res.ok || !json || json.error) {
    throw new ApiError(json?.error?.code ?? "UNKNOWN", json?.error?.message ?? "ระบบขัดข้อง ลองใหม่อีกครั้ง", res.status);
  }
  return json.data;
}
