"use client";

import Link from "next/link";
import { Clock3, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { listJobs, type Job } from "@/lib/api";
import { ProgressBar, StatusBadge } from "@/components/StatusBadge";

const STATUSES = ["", "uploaded", "queued", "processing", "completed", "failed", "canceled"];
const STATUS_FILTER_LABELS: Record<string, string> = {
  "": "全部状态",
  uploaded: "已上传",
  queued: "排队中",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
  canceled: "已取消",
};
const MODE_LABELS: Record<string, string> = {
  general: "通用文档",
  paper: "论文 / 手册",
  invoice: "发票",
  contract: "合同",
  screenshot: "截图",
};

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        setJobs(await listJobs({ q, status_filter: status }));
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [q, status]);

  const completedCount = jobs.filter((job) => job.status === "completed").length;

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">历史记录</span>
          <h1>历史</h1>
          <p>搜索过去上传的文件，按状态筛选，并重新打开审校页面。</p>
        </div>
      </div>

      <section className="summary-grid">
        <div className="summary-card">
          <Clock3 size={18} />
          <div>
            <strong>{jobs.length}</strong>
            <span>匹配到的任务</span>
          </div>
        </div>
        <div className="summary-card">
          <StatusBadge status="completed" />
          <div>
            <strong>{completedCount}</strong>
            <span>当前列表已完成</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-body">
          <div className="toolbar filter-bar" style={{ marginBottom: 14 }}>
            <div className="search-field">
              <Search size={18} />
              <input placeholder="搜索文件名" value={q} onChange={(event) => setQ(event.target.value)} />
            </div>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {STATUSES.map((item) => (
                <option key={item || "all"} value={item}>
                  {STATUS_FILTER_LABELS[item]}
                </option>
              ))}
            </select>
          </div>

          {loading && <p className="muted">历史记录加载中...</p>}
          {!loading && jobs.length === 0 && <p className="muted">没有找到匹配的任务。</p>}
          {jobs.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>状态</th>
                  <th>进度</th>
                  <th>模式</th>
                  <th>创建时间</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.file?.original_name || job.file_id}</td>
                    <td>
                      <StatusBadge status={job.status} />
                    </td>
                    <td>
                      <ProgressBar value={job.progress} />
                    </td>
                    <td>{MODE_LABELS[job.mode] || job.mode}</td>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                    <td>
                      <Link href={`/results/${job.id}`}>
                        <button>打开</button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </main>
  );
}
