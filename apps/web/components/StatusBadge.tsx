import type { JobStatus } from "@/lib/api";

const STATUS_LABELS: Record<JobStatus, string> = {
  uploaded: "已上传",
  queued: "排队中",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return <span className={`status ${status}`}>{STATUS_LABELS[status]}</span>;
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="progress" aria-label={`进度 ${value}%`}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
