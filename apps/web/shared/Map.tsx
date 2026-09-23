"use client";

import dynamic from "next/dynamic";

// Leaflet ใช้ window เลยต้องปิด SSR ทุกหน้าใช้ตัวนี้
const Map = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="status" style={{ height: 480 }}>กำลังโหลดแผนที่...</div>,
});

export default Map;
export type { MapMarker, MapRoute, Bounds } from "./MapView";
