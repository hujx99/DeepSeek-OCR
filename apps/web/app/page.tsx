"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardPaste, FileUp, Files, Play, ScanText, Trash2 } from "lucide-react";
import { createJob, uploadFile } from "@/lib/api";

const MODES = [
  { value: "general", label: "通用文档" },
  { value: "paper", label: "论文 / 手册" },
  { value: "invoice", label: "发票" },
  { value: "contract", label: "合同" },
  { value: "screenshot", label: "截图" },
];
const FORMATS = [
  { value: "markdown", label: "Markdown" },
  { value: "txt", label: "TXT 文本" },
  { value: "json", label: "JSON" },
  { value: "xlsx", label: "Excel" },
];

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function getFormatLabel(value: string) {
  return FORMATS.find((item) => item.value === value)?.label || value.toUpperCase();
}

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState("general");
  const [outputFormat, setOutputFormat] = useState("markdown");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const canSubmit = files.length > 0 && !busy;
  const totalSize = useMemo(() => files.reduce((sum, file) => sum + file.size, 0), [files]);

  function addFiles(next: FileList | File[]) {
    setMessage(null);
    setFiles((current) => [...current, ...Array.from(next)]);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    addFiles(event.dataTransfer.files);
  }

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) addFiles(event.target.files);
    event.target.value = "";
  }

  function openFilePicker() {
    inputRef.current?.click();
  }

  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const clipboardItems = Array.from(event.clipboardData?.items || []);
      const clipboardFiles = Array.from(event.clipboardData?.files || []);
      const pastedFiles = clipboardItems
        .map((item) => item.getAsFile())
        .filter((file): file is File => Boolean(file));

      const nextFiles = [...clipboardFiles, ...pastedFiles].filter(
        (file, index, collection) => collection.findIndex((entry) => entry.name === file.name && entry.size === file.size) === index,
      );

      if (nextFiles.length === 0) return;
      event.preventDefault();
      addFiles(nextFiles);
      setMessage(`已从剪贴板添加 ${nextFiles.length} 个文件`);
    }

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  async function submit() {
    setBusy(true);
    setMessage(null);
    try {
      const created = [];
      for (const file of files) {
        const uploaded = await uploadFile(file);
        const job = await createJob({
          file_id: uploaded.id,
          mode,
          output_format: outputFormat,
          template_type: ["invoice", "contract"].includes(mode) ? mode : null,
        });
        created.push(job);
      }
      router.push(created.length === 1 ? `/results/${created[0].id}` : "/jobs");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">上传入口</span>
          <h1>上传文档</h1>
          <p>上传 PDF 或图片后进入 OCR 队列，完成后可在线审校并导出最终结果。</p>
        </div>
        <button className="primary" disabled={!canSubmit} onClick={submit}>
          <Play size={16} /> 开始处理
        </button>
      </div>

      <div className="grid two">
        <section className="panel">
          <div className="panel-body">
            <div className="dropzone" onClick={openFilePicker} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
              <div className="dropzone-badge">OCR 上传区</div>
              <FileUp size={34} />
              <strong>拖拽文件到这里</strong>
              <span className="muted">支持 PDF、PNG、JPG、JPEG、WebP。点击此区域任意位置也可以直接选择文件。</span>
              <div className="toolbar" style={{ justifyContent: "center" }}>
                <input
                  accept=".pdf,.png,.jpg,.jpeg,.webp"
                  multiple
                  onChange={onPick}
                  ref={inputRef}
                  style={{ display: "none" }}
                  type="file"
                />
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    openFilePicker();
                  }}
                  type="button"
                >
                  <FileUp size={16} /> 选择文件
                </button>
              </div>
              <span className="muted dropzone-note">
                <ClipboardPaste size={14} style={{ verticalAlign: "text-bottom" }} /> 也可以直接按 Cmd+V / Ctrl+V，把截图或复制的图片粘贴到当前页面。
              </span>
            </div>
          </div>
        </section>

        <aside className="panel">
          <div className="panel-body editor-stack">
            <label className="editor-stack">
              <span>识别模式</span>
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                {MODES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="editor-stack">
              <span>默认导出格式</span>
              <select value={outputFormat} onChange={(event) => setOutputFormat(event.target.value)}>
                {FORMATS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">{files.length ? `已选择 ${files.length} 个文件，共 ${formatBytes(totalSize)}` : "还没有选择文件。"}</p>
            <div className="mini-stats">
              <div className="mini-stat">
                <Files size={16} />
                <div>
                  <strong>{files.length}</strong>
                  <span>待提交文件</span>
                </div>
              </div>
              <div className="mini-stat">
                <ScanText size={16} />
                <div>
                  <strong>{getFormatLabel(outputFormat)}</strong>
                  <span>主要导出格式</span>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="panel-body">
          <div className="toolbar" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <strong>文件列表</strong>
            {files.length > 0 && (
              <button onClick={() => setFiles([])}>
                <Trash2 size={15} /> 清空
              </button>
            )}
          </div>
          {files.length === 0 ? (
            <p className="muted">已选择的文件会在提交前显示在这里。</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>文件名</th>
                  <th>大小</th>
                  <th>类型</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {files.map((file, index) => (
                  <tr key={`${file.name}-${index}`}>
                    <td>{file.name}</td>
                    <td>{formatBytes(file.size)}</td>
                    <td>{file.type || "unknown"}</td>
                    <td>
                      <button onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))}>
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {message && <p style={{ color: "var(--danger)" }}>{message}</p>}
        </div>
      </section>
    </main>
  );
}
