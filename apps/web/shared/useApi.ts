"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";

// ดึงข้อมูลตอนเปิดหน้า ได้ครบ 3 สถานะที่ CONTRACT หัวข้อ 7 บังคับ
// ตัวอย่าง: const { data, error, loading, reload } = useApi<Trip[]>("/trips")
// ส่ง path เป็น null ถ้ายังไม่พร้อมจะดึง (เช่น ยังไม่รู้ตำแหน่ง)
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(path !== null);

  const reload = useCallback(async () => {
    if (path === null) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api<T>(path));
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("INTERNAL_ERROR", "เกิดข้อผิดพลาด"));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
