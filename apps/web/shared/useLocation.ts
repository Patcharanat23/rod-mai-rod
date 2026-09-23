"use client";

import { useEffect, useState } from "react";
import type { LatLng } from "./types";

const BANGKOK: LatLng = { lat: 13.7563, lng: 100.5018 };

// ตำแหน่งผู้ใช้ ถ้าไม่อนุญาต/เปิดผ่าน http ที่ไม่ใช่ localhost/รอเกิน 5 วินาที ใช้กรุงเทพแทน ห้ามค้าง
export function useLocation() {
  const [pos, setPos] = useState<LatLng | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    const fallback = () => {
      setDenied(true);
      setPos((p) => p ?? BANGKOK);
    };
    if (!navigator.geolocation) return fallback();
    const timer = setTimeout(fallback, 5000);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        clearTimeout(timer);
        setPos({ lat: p.coords.latitude, lng: p.coords.longitude });
      },
      () => {
        clearTimeout(timer);
        fallback();
      },
      { timeout: 5000 },
    );
    return () => clearTimeout(timer);
  }, []);

  return { pos, denied };
}
