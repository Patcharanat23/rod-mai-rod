// ตัวเรียก API กลาง ทุกหน้าต้องเรียกผ่านไฟล์นี้เท่านั้น
// แนบ token, สร้าง X-Request-ID, แกะ {data, error} และเจอ 401 พากลับหน้า login

const TOKEN_KEY = "rmr_token";

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function logout() {
  setToken(null);
  window.location.href = "/login";
}

type Options = { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown };

// ตัวอย่าง: const trips = await api<Trip[]>("/trips")
//          await api<Trip>(`/trips/${id}`, { method: "PATCH", body: { departure_time } })
export async function api<T>(path: string, { method = "GET", body }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Request-ID": crypto.randomUUID() };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่");
  }

  let json: { data: T; error: { code: string; message: string } | null };
  try {
    json = await res.json();
  } catch {
    throw new ApiError("INTERNAL_ERROR", "เซิร์ฟเวอร์ตอบกลับผิดรูปแบบ");
  }

  if (json.error) {
    if (json.error.code === "UNAUTHORIZED" && !path.startsWith("/auth/")) logout();
    throw new ApiError(json.error.code, json.error.message);
  }
  return json.data;
}
