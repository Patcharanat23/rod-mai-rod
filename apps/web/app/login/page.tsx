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
    <div className="login">
      <section className="login-hero">
        <div className="brand">
          <img src="/mascot/nong-taem-icon.png" alt="" />
          <span>
            <strong>รอดไม่รอด</strong>
            <small>rod-mai-rod</small>
          </span>
        </div>
        <p className="eyebrow">Your safer way forward</p>
        <h1>
          ทุกเส้นทาง
          <br />
          รอดได้ ถ้าวางแผนดี
        </h1>
        <p className="muted">เช็กเส้นทาง อากาศ และความปลอดภัยก่อนออกเดินทางไปกับน้องแต้ม</p>
        <img className="login-mascot" src="/mascot/nong-taem-fullbody.png" alt="น้องแต้ม มาสคอตของรอดไม่รอด" />
      </section>
      <section className="login-form">
        <p className="eyebrow">{mode === "login" ? "ยินดีต้อนรับกลับ" : "เริ่มต้นใช้งาน"}</p>
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
      </section>
    </div>
  );
}
