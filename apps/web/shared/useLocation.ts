"use client";

import { useEffect, useState } from "react";
import type { LatLng } from "./types";

export const BANGKOK: LatLng = { lat: 13.7563, lng: 100.5018 };
const THAILAND = { minLat: 5.6, minLng: 97.3, maxLat: 20.5, maxLng: 105.7 }; // กรอบเดียวกับ geo.py ของ service

export function inThailand(p: LatLng): boolean {
  return p.lat >= THAILAND.minLat && p.lat <= THAILAND.maxLat && p.lng >= THAILAND.minLng && p.lng <= THAILAND.maxLng;
}

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
