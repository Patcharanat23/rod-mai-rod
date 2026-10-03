"use client";

import dynamic from "next/dynamic";

// Leaflet ใช้ window ต้องปิด SSR
const Map = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="muted" style={{ display: "grid", placeItems: "center", height: "100%" }}>กำลังโหลดแผนที่...</div>,
});

export default Map;
export type { MapPin, MapRoute, MapDot } from "./MapView";
