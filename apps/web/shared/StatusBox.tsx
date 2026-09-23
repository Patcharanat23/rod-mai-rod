import type { ApiError } from "./api";

// ใช้คู่กับ useApi: ถ้าคืนค่าไม่ใช่ null ให้แสดงตัวนี้แทนเนื้อหา
// if (loading || error || !data) return <StatusBox loading={loading} error={error} onRetry={reload} empty="ยังไม่มีทริป" />
export default function StatusBox({
  loading,
  error,
  onRetry,
  empty = "ไม่มีข้อมูล",
}: {
  loading?: boolean;
  error?: ApiError | null;
  onRetry?: () => void;
  empty?: string;
}) {
  if (loading) return <div className="status">กำลังโหลด...</div>;
  if (error)
    return (
      <div className="status status-error">
        {error.message}
        {onRetry && (
          <button className="btn" onClick={onRetry}>
            ลองใหม่
          </button>
        )}
      </div>
    );
  return <div className="status">{empty}</div>;
}
