import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "域灵 YuLing — AI 数字员工",
  description: "AI短视频创作 · 智能对话 · 知识库 · SOP工作流",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen bg-[var(--surface)] text-[var(--text-primary)] font-sans">
        <Sidebar />
        <main className="flex-1 ml-[260px] min-h-screen">{children}</main>
      </body>
    </html>
  );
}
