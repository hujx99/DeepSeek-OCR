"use client";

import Link from "next/link";
import { AlertTriangle, RotateCcw, ScanSearch, TimerReset } from "lucide-react";
import { useEffect, useState } from "react";
import { listJobs, retryJob, type Job } from "@/lib/api";
import { ProgressBar, StatusBadge } from "@/components/StatusBadge";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const data = await listJobs();
      setJobs(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, []);

  async function onRetry(jobId: string) {
    await retryJob(jobId);
    await refresh();
  }

  const activeCount = jobs.filter((job) => ["queued", "processing", "uploaded"].includes(job.status)).length;
  const failedCount = jobs.filter((job) => job.status === "failed").length;
  const completedCount = jobs.filter((job) => job.status === "completed").length;
  const modeLabels: Record<string, string> = {
    general: "通用文档",
    paper: "论文 / 手册",
    invoice: "发票",
    contract: "合同",
    screenshot: "截图",
  };

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">任务队列</span>
          <h1>任务</h1>
          <p>查看 OCR 处理进度、失败原因，并重新打开已完成的结果页面。</p>
        </div>
      </div>

      <section className="summary-grid">
        <div className="summary-card">
          <ScanSearch size={18} />
          <div>
            <strong>{jobs.length}</strong>
            <span>任务总数</span>
          </div>
        </div>
        <div className="summary-card">
          <TimerReset size={18} />
          <div>
            <strong>{activeCount}</strong>
            <span>当前处理中</span>
          </div>
        </div>
        <div className="summary-card">
          <AlertTriangle size={18} />
          <div>
            <strong>{failedCount}</strong>
            <span>待重试</span>
          </div>
        </div>
        <div className="summary-card">
          <StatusBadge status="completed" />
          <div>
            <strong>{completedCount}</strong>
            <span>Completed</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-body">
          {loading && <p className="muted">任务加载中...</p>}
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
          {!loading && jobs.length === 0 && <p className="muted">还没有任务，先去上传文档开始处理。</p>}
          {jobs.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>状态</th>
                  <th>进度</th>
                  <th>模式</th>
                  <th>更新时间</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.file?.original_name || job.file_id}</td>
                    <td>
                      <StatusBadge status={job.status} />
                      {job.error_message && <div style={{ color: "var(--danger)", marginTop: 6 }}>{job.error_message}</div>}
                    </td>
                    <td>
                      <ProgressBar value={job.progress} />
                    </td>
                    <td>{modeLabels[job.mode] || job.mode}</td>
                    <td>{new Date(job.updated_at).toLocaleString()}</td>
                    <td className="toolbar">
                      <Link href={`/results/${job.id}`}>
                        <button>打开</button>
                      </Link>
                      {job.status === "failed" && (
                        <button onClick={() => onRetry(job.id)}>
                          <RotateCcw size={15} /> 重试
                        </button>
                      )}
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
