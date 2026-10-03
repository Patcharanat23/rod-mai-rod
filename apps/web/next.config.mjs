// ห้ามใส่ rewrites ที่นี่ การส่งต่อ /api/v1 อยู่ใน app/api/v1/[...path]/route.ts (CONTRACT หัวข้อ 7)
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
