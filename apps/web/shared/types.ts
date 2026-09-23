// ชนิดข้อมูลตาม docs/CONTRACT.md หัวข้อ 4 และ 6 ถ้า CONTRACT เปลี่ยน แก้ที่นี่ที่เดียว

export type LatLng = { lat: number; lng: number };
export type Place = LatLng & { name?: string | null };

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type Recommendation = "NORMAL" | "DELAY" | "REROUTE" | "AVOID";
export type PlanStatus = "NONE" | "FRESH" | "STALE";
export type Warning =
  | "WEATHER_UNAVAILABLE"
  | "HAZARD_FEED_UNAVAILABLE"
  | "ALTERNATIVE_ROUTES_UNAVAILABLE"
  | "FORECAST_OUT_OF_RANGE"
  | "LLM_UNAVAILABLE";

export type Forecast = {
  time: string;
  rain_mm_per_h: number;
  wind_kmh: number;
  temp_c: number;
  condition_th: string;
};

export type User = { user_id: string; email: string };

export type RouteOption = {
  route_id: string;
  duration_min: number;
  distance_km: number;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  is_recommended: boolean;
  geometry: LatLng[];
};

export type PlanWaypoint = {
  waypoint_id: string;
  kind: "ORIGIN" | "STOP" | "DESTINATION";
  name: string;
  lat: number;
  lng: number;
  eta: string;
  forecast: Forecast | null;
  risk_level: RiskLevel | null;
};

export type TripPlan = {
  trip_id: string;
  trip_no: number;
  departure_time: string;
  arrival_time: string;
  duration_min: number;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  recommendation: Recommendation;
  summary_th: string;
  route_options: RouteOption[];
  waypoints: PlanWaypoint[];
  warnings: Warning[];
};

export type Trip = {
  trip_id: string;
  trip_no: number;
  origin: Place;
  destination: Place;
  departure_time: string;
  waypoints: Place[];
  plan_status: PlanStatus;
  plan: TripPlan | null;
};

export type TripInput = {
  origin: Place;
  destination: Place;
  departure_time: string;
  waypoints: Place[];
};

export type AreaWeather = {
  center: LatLng;
  cells: (LatLng & { forecast: Forecast })[];
  updated_at: string | null;
  warnings: Warning[];
};

export type HazardType = "RAIN" | "HEAVY_RAIN" | "STRONG_WIND" | "FLOOD" | "LANDSLIDE_RISK" | "STORM" | "EARTHQUAKE";

export type Hazard = LatLng & {
  hazard_id: string;
  hazard_type: HazardType | string;
  severity: RiskLevel;
  province: string;
  title_th: string;
  source: "OPEN_METEO" | "GDACS" | "USGS" | "THAIWATER" | "TMD" | "DERIVED" | string;
  updated_at: string;
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type ChatAction = {
  type: "TRIP_CREATED" | "TRIP_UPDATED" | "TRIP_DELETED";
  trip_id: string;
  trip_no: number;
};

export type ChatReply = { reply: string; actions: ChatAction[]; warnings: Warning[] };

export type Emergency = {
  hazard_type: HazardType;
  steps_th: string[];
  contacts: { name_th: string; phone: string }[];
};
