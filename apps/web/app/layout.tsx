import type { Metadata } from "next";
import Link from "next/link";
import { AppNav } from "@/components/AppNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocFlow OCR",
  description: "上传文档，进行 OCR 审校，并导出结果。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <div className="app-backdrop" />
          <header className="topbar-shell">
            <div className="topbar">
              <Link className="brand" href="/">
                <span className="brand-mark">DF</span>
                <span>
                  <strong>DocFlow OCR</strong>
                  <small>异步识别与审校工作台</small>
                </span>
              </Link>
              <AppNav />
            </div>
          </header>
          <div className="page-shell">{children}</div>
        </div>
      </body>
    </html>
  );
}
