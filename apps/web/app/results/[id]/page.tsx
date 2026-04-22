"use client";

import { useParams } from "next/navigation";
import { Check, Download, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL, exportJob, getJobResult, updateResult, type JobResult, type PageResult } from "@/lib/api";
import { ProgressBar, StatusBadge } from "@/components/StatusBadge";

const EXPORTS = ["markdown", "txt", "json", "xlsx"];

export default function ResultPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const [result, setResult] = useState<JobResult | null>(null);
  const [pageNo, setPageNo] = useState(1);
  const [reviewedText, setReviewedText] = useState("");
  const [reviewedMarkdown, setReviewedMarkdown] = useState("");
  const [reviewedJson, setReviewedJson] = useState("{}");
  const [active, setActive] = useState<"markdown" | "text" | "json">("markdown");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const skipAutosave = useRef(true);

  const page = useMemo<PageResult | undefined>(() => result?.pages.find((item) => item.page_no === pageNo), [result, pageNo]);
  const fileUrl = result?.job.file ? `${API_BASE_URL}/api/files/${result.job.file.id}/download` : "";

  async function refresh() {
    try {
      const data = await getJobResult(jobId);
      setResult(data);
      setError(null);
      if (!data.pages.find((item) => item.page_no === pageNo) && data.pages[0]) {
        setPageNo(data.pages[0].page_no);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "结果加载失败");
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(() => {
      if (!result || ["queued", "processing", "uploaded"].includes(result.job.status)) refresh();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [jobId, result?.job.status]);

  useEffect(() => {
    skipAutosave.current = true;
    setReviewedText(page?.reviewed_text || page?.raw_text || "");
    setReviewedMarkdown(page?.reviewed_markdown || page?.raw_markdown || "");
    setReviewedJson(JSON.stringify(result?.structured_result?.reviewed_json || {}, null, 2));
    window.setTimeout(() => {
      skipAutosave.current = false;
    }, 0);
  }, [page?.id, result?.structured_result?.id]);

  useEffect(() => {
    if (!page || skipAutosave.current) return;
    const timer = window.setTimeout(() => save("已自动保存"), 900);
    return () => window.clearTimeout(timer);
  }, [reviewedText, reviewedMarkdown]);

  async function save(message = "已保存") {
    if (!page) return;
    setSaving(true);
    try {
      const next = await updateResult(jobId, {
        page_no: page.page_no,
        reviewed_text: reviewedText,
        reviewed_markdown: reviewedMarkdown,
      });
      setResult(next);
      setToast(message);
      window.setTimeout(() => setToast(null), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function saveJson() {
    try {
      const parsed = JSON.parse(reviewedJson) as Record<string, unknown>;
      setSaving(true);
      const next = await updateResult(jobId, { reviewed_json: parsed });
      setResult(next);
      setToast("结构化结果已保存");
      window.setTimeout(() => setToast(null), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "JSON 格式不正确");
    } finally {
      setSaving(false);
    }
  }

  async function confirmPage() {
    if (!page) return;
    const next = await updateResult(jobId, { page_no: page.page_no, is_confirmed: !page.is_confirmed });
    setResult(next);
  }

  async function download(format: string) {
    try {
      const response = await exportJob(jobId, format);
      window.location.href = `${API_BASE_URL}${response.download_url}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">结果审校</span>
          <h1>审校结果</h1>
          <p>{result?.job.file?.original_name || jobId}</p>
        </div>
        {result && (
          <div className="toolbar">
            <StatusBadge status={result.job.status} />
            <ProgressBar value={result.job.progress} />
          </div>
        )}
      </div>

      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {!result && !error && <section className="panel"><div className="panel-body muted">结果加载中...</div></section>}
      {result && result.job.status !== "completed" && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-body">
            <p className="muted">
              OCR 当前状态为「{result.job.status}」，页面会持续刷新，直到处理完成。
            </p>
          </div>
        </section>
      )}

      {result && (
        <div className="result-layout">
          <section className="panel">
            <div className="panel-body">
              <div className="toolbar" style={{ justifyContent: "space-between", marginBottom: 12 }}>
                <strong>原文预览</strong>
                <div className="toolbar">
                  <span className="section-pill">页码</span>
                  <select value={pageNo} onChange={(event) => setPageNo(Number(event.target.value))}>
                    {(result.pages.length ? result.pages : [{ page_no: 1 } as PageResult]).map((item) => (
                      <option key={item.page_no} value={item.page_no}>
                        {item.page_no}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="preview">
                {result.job.file?.mime_type === "application/pdf" ? (
                  <iframe src={`${fileUrl}#page=${pageNo}`} title="PDF preview" />
                ) : (
                  <img alt="上传文件预览" src={fileUrl} />
                )}
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-body editor-stack">
              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <div className="toolbar segmented">
                  <button className={active === "markdown" ? "primary" : ""} onClick={() => setActive("markdown")}>Markdown</button>
                  <button className={active === "text" ? "primary" : ""} onClick={() => setActive("text")}>纯文本</button>
                  <button className={active === "json" ? "primary" : ""} onClick={() => setActive("json")}>JSON</button>
                </div>
                <button onClick={confirmPage} disabled={!page}>
                  <Check size={15} /> {page?.is_confirmed ? "已确认" : "确认"}
                </button>
              </div>

              {active === "markdown" && (
                <textarea value={reviewedMarkdown} onChange={(event) => setReviewedMarkdown(event.target.value)} />
              )}
              {active === "text" && <textarea value={reviewedText} onChange={(event) => setReviewedText(event.target.value)} />}
              {active === "json" && <textarea value={reviewedJson} onChange={(event) => setReviewedJson(event.target.value)} />}

              <div className="toolbar" style={{ justifyContent: "space-between" }}>
                <div className="toolbar">
                  <button onClick={() => (active === "json" ? saveJson() : save())} disabled={saving || !page}>
                    <Save size={15} /> {saving ? "保存中" : "保存"}
                  </button>
                  <span className="muted">{page?.is_confirmed ? "当前页已确认" : "当前页未确认"}</span>
                </div>
                <div className="toolbar">
                  {EXPORTS.map((format) => (
                    <button key={format} onClick={() => download(format)} disabled={result.job.status !== "completed"}>
                      <Download size={15} /> {format.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
      {toast && <div className="toast">{toast}</div>}
    </main>
  );
}
