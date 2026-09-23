"use client";

// แผนที่ตัวเดียวของทั้งเว็บ อย่า import ไฟล์นี้ตรงๆ ให้ใช้ Map จาก "@/shared/Map" (ปิด SSR ให้แล้ว)
import "leaflet/dist/leaflet.css";
import { useEffect, type ReactNode } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import type { LatLng } from "./types";

export type MapRoute = {
  id: string;
  points: LatLng[];
  color?: string;
  highlighted?: boolean;
  onClick?: () => void;
};

export type MapMarker = {
  id: string;
  lat: number;
  lng: number;
  color?: string;
  popup?: ReactNode;
  onClick?: () => void;
};

export type Bounds = { min_lat: number; min_lng: number; max_lat: number; max_lng: number };

export type MapViewProps = {
  center?: LatLng;
  zoom?: number;
  routes?: MapRoute[];
  markers?: MapMarker[];
  fitTo?: LatLng[]; // ซูมให้เห็นจุดพวกนี้ทั้งหมด
  onBoundsChange?: (b: Bounds) => void; // เรียกหลังผู้ใช้เลื่อน/ซูมเสร็จ
  onMapClick?: (p: LatLng) => void; // ให้ผู้ใช้จิ้มเลือกตำแหน่ง
  height?: number | string;
};

const BANGKOK: LatLng = { lat: 13.7563, lng: 100.5018 };
const toLeaflet = (p: LatLng): [number, number] => [p.lat, p.lng];

function FitTo({ points }: { points?: LatLng[] }) {
  const map = useMap();
  const key = JSON.stringify(points ?? []);
  useEffect(() => {
    if (!points || points.length === 0) return;
    if (points.length === 1) map.setView(toLeaflet(points[0]), 11);
    else map.fitBounds(points.map(toLeaflet) as LatLngBoundsExpression, { padding: [30, 30] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

function ClickWatcher({ onClick }: { onClick: (p: LatLng) => void }) {
  useMapEvents({ click: (e) => onClick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function BoundsWatcher({ onChange }: { onChange: (b: Bounds) => void }) {
  const map = useMapEvents({
    moveend: () => emit(),
  });
  const emit = () => {
    const b = map.getBounds();
    onChange({ min_lat: b.getSouth(), min_lng: b.getWest(), max_lat: b.getNorth(), max_lng: b.getEast() });
  };
  useEffect(emit, []); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function MapView({
  center = BANGKOK,
  zoom = 6,
  routes = [],
  markers = [],
  fitTo,
  onBoundsChange,
  onMapClick,
  height = 480,
}: MapViewProps) {
  // เส้นที่ highlighted วาดทีหลังให้อยู่บนสุด
  const ordered = [...routes].sort((a, b) => Number(!!a.highlighted) - Number(!!b.highlighted));
  return (
    <MapContainer center={toLeaflet(center)} zoom={zoom} style={{ height, width: "100%", borderRadius: 8 }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {ordered.map((r) => (
        <Polyline
          key={r.id}
          positions={r.points.map(toLeaflet)}
          pathOptions={{ color: r.color ?? "#2563eb", weight: r.highlighted ? 7 : 4, opacity: r.highlighted ? 1 : 0.5 }}
          eventHandlers={r.onClick ? { click: r.onClick } : undefined}
        />
      ))}
      {markers.map((m) => (
        <CircleMarker
          key={m.id}
          center={[m.lat, m.lng]}
          radius={9}
          pathOptions={{ color: "#fff", weight: 2, fillColor: m.color ?? "#2563eb", fillOpacity: 1 }}
          eventHandlers={m.onClick ? { click: m.onClick } : undefined}
        >
          {m.popup && <Popup>{m.popup}</Popup>}
        </CircleMarker>
      ))}
      <FitTo points={fitTo} />
      {onBoundsChange && <BoundsWatcher onChange={onBoundsChange} />}
      {onMapClick && <ClickWatcher onClick={onMapClick} />}
    </MapContainer>
  );
}
