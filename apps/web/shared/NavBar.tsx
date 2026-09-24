"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "./api";
import { useApi } from "./useApi";
import type { User } from "./types";

const TABS = [
  { href: "/overview", label: "ภาพรวม", icon: "home" },
  { href: "/my-trip", label: "ทริปของฉัน", icon: "route" },
  { href: "/safety-map", label: "แผนที่จุดเสี่ยงภัย", icon: "safety" },
  { href: "/assistant", label: "คุยกับน้องแต้ม", icon: "chat" },
];

export function Icon({ name }: { name: string }) {
  return <span className="icon" style={{ ["--src" as string]: `url(/icons/${name}.svg)` }} aria-hidden />;
}

export default function NavBar() {
  const path = usePathname();
  const { data: user } = useApi<User>(path === "/login" ? null : "/me");
  if (path === "/login") return null;
  return (
    <>
      <header className="topbar">
        <Link href="/overview" className="brand">
          <img src="/mascot/nong-taem-icon.png" alt="" />
          <span>
            <strong>รอดไม่รอด</strong>
            <small>rod-mai-rod</small>
          </span>
        </Link>
        <div className="user">
          <span className="muted">{user?.email}</span>
          <img src="/mascot/nong-taem-avatar.png" alt="" />
          <button className="btn btn-link" onClick={logout}>
            ออกจากระบบ
          </button>
        </div>
      </header>
      <nav className="sidebar" aria-label="เมนูหลัก">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            aria-label={t.label}
            className={`side-link ${path.startsWith(t.href) ? "active" : ""}`}
          >
            <Icon name={t.icon} />
            <span className="tip">{t.label}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
