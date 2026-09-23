"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "./api";

const TABS = [
  { href: "/overview", label: "Overview" },
  { href: "/my-trip", label: "My Trip" },
  { href: "/safety-map", label: "Safety Map" },
  { href: "/assistant", label: "Assistant" },
];

export default function NavBar() {
  const path = usePathname();
  if (path === "/login") return null;
  return (
    <nav className="nav">
      <strong>rod-mai-rod</strong>
      {TABS.map((t) => (
        <Link key={t.href} href={t.href} className={path.startsWith(t.href) ? "active" : ""}>
          {t.label}
        </Link>
      ))}
      <button className="btn btn-link" onClick={logout}>
        ออกจากระบบ
      </button>
    </nav>
  );
}
