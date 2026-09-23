"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, setToken } from "@/shared/api";
import type { User } from "@/shared/types";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") await api("/auth/register", { method: "POST", body: { email, password } });
      const res = await api<{ token: string; user: User }>("/auth/login", { method: "POST", body: { email, password } });
      setToken(res.token);
      router.push("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "เข้าสู่ระบบไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 400, margin: "80px auto" }}>
      <h2>{mode === "login" ? "เข้าสู่ระบบ" : "สมัครสมาชิก"}</h2>
      <form onSubmit={submit}>
        <label>
          อีเมล
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          รหัสผ่าน (อย่างน้อย 6 ตัว)
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
        </label>
        {error && <p className="error-text">{error}</p>}
        <button className="btn" disabled={busy} style={{ width: "100%" }}>
          {busy ? "กำลังดำเนินการ..." : mode === "login" ? "เข้าสู่ระบบ" : "สมัครและเข้าสู่ระบบ"}
        </button>
      </form>
      <p className="muted">
        {mode === "login" ? "ยังไม่มีบัญชี? " : "มีบัญชีแล้ว? "}
        <button className="btn-link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "สมัครสมาชิก" : "เข้าสู่ระบบ"}
        </button>
      </p>
    </div>
  );
}
