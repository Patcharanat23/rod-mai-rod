// ไอคอนเส้นขนาด 24 ใช้สีตามตัวอักษร (currentColor) ทุกไอคอนในเว็บมาจากไฟล์นี้
const P: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5M5 9.5V21h5v-6h4v6h5V9.5",
  route: "M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm12-10a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM6 15V9a4 4 0 0 1 4-4h2M18 9v6a4 4 0 0 1-4 4h-2",
  map: "M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Zm0 0v13m6-10.5v13",
  shield: "M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Zm-3 9 2 2 4-4",
  sos: "M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Zm0 5v5m0 3h.01",
  chat: "M4 5h16v11H8l-4 4V5Zm4 5h.01M12 10h.01M16 10h.01",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4l2-2Zm4 4a2 2 0 0 0 4 0",
  rain: "M7 15a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 6.5 4 4 0 0 1 17.5 15M8 18l-1 2m5-2-1 2m5-2-1 2",
  heavyrain: "M7 13a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 4.5 4 4 0 0 1 17.5 13M8 15l-2 5m6-5-2 5m6-5-2 5",
  wind: "M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8",
  flood: "M3 17c2 0 2-1.5 4.5-1.5S9.5 17 12 17s2-1.5 4.5-1.5S18.5 17 21 17M3 21c2 0 2-1.5 4.5-1.5S9.5 21 12 21s2-1.5 4.5-1.5S18.5 21 21 21M6 12V7l6-4 6 4v5",
  landslide: "M3 20h18L14 7l-3 5-2-3-6 11Zm11-4h.01M10 17h.01",
  storm: "M7 14a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 5.5 4 4 0 0 1 17.5 14M13 11l-3 5h4l-3 5",
  quake: "M3 12h3l2-5 3 10 3-8 2 3h5",
  sun: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.7-5.7 1.4-1.4M4.9 19.1l1.4-1.4m11.4 1.4-1.4-1.4M4.9 4.9l1.4 1.4M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
  cloud: "M7 18a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 9.5 4 4 0 0 1 17.5 18H7Z",
  cloudoff: "M7 18a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 9.5 4 4 0 0 1 17.5 18H7ZM4 4l16 16",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v4l3 2",
  pin: "M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  flag: "M5 21V4m0 0h11l-2 4 2 4H5",
  plus: "M12 5v14M5 12h14",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 4 4",
  x: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5 10 17l9-10",
  alert: "M12 4 2.5 20h19L12 4Zm0 6v4m0 3h.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v6m0-9h.01",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z",
  share: "M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8.6 13.5l6.8 4M15.4 6.5l-6.8 4",
  edit: "M4 20h4L19 9l-4-4L4 16v4Zm10-14 4 4",
  trash: "M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3",
  locate: "M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm0-4a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm0-13v3m0 14v3M2 12h3m14 0h3",
  layers: "M12 3 2 8l10 5 10-5-10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5",
  chevron: "M9 6l6 6-6 6",
  back: "M15 6l-6 6 6 6",
  calendar: "M4 6h16v15H4V6Zm0 5h16M8 3v5m8-5v5",
  car: "M5 16v3h3v-2h8v2h3v-3M5 16h14M5 16l1.5-6A2 2 0 0 1 8.4 8.5h7.2a2 2 0 0 1 1.9 1.5L19 16M7.5 13h.01M16.5 13h.01",
  spark: "M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M6 18l2.5-2.5m7-7L18 6",
  send: "M4 12 20 4l-6 16-3-7-7-1Z",
  logout: "M15 4h4v16h-4M10 16l-4-4 4-4M6 12h11",
  thermo: "M10 13V5a2 2 0 1 1 4 0v8a4 4 0 1 1-4 0Z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z",
  compass: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm3.5-12.5-2 5-5 2 2-5 5-2Z",
  mail: "M4 6h16v12H4V6Zm0 0 8 7 8-7",
  lock: "M6 11h12v10H6V11Zm2 0V8a4 4 0 1 1 8 0v3",
  checklist: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
};

export default function Icon({ name, size = 20, stroke = 1.8, className }: { name: string; size?: number; stroke?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={P[name] ?? P.info} />
    </svg>
  );
}
