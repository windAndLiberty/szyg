"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { healthCheck } from "@/lib/api";

export default function Dashboard() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    healthCheck().then(setStatus).catch(() => setStatus(null));
  }, []);

  const cards = [
    { icon: "◈", title: "智能对话", desc: "多模型 AI 对话 · OpenRouter · Ollama · ModelScope", href: "/chat", color: "#6366f1" },
    { icon: "🎬", title: "视频创作", desc: "一键生成短视频：脚本 → 封面 → 配音 → 合成", href: "/video", color: "#f59e0b" },
    { icon: "📚", title: "知识库", desc: "上传文档，AI自动学习，精准检索上下文", href: "/knowledge", color: "#22c55e" },
    { icon: "📋", title: "SOP 管理", desc: "定义标准操作流程，AI按流程自动执行", href: "/sop", color: "#ec4899" },
    { icon: "⚙️", title: "系统设置", desc: "管理 API Key、模型配置、后端切换", href: "/settings", color: "#8888aa" },
  ];

  return (
    <div className="animate-fade-in">
      <div style={{ padding: "32px 40px 0" }}>
        <h1 style={{ fontSize: 32, margin: 0, fontWeight: 700 }}>
          <span className="gradient-text">域灵 AI 数字员工</span>
        </h1>
        <p style={{ color: "var(--text-secondary)", marginTop: 8, fontSize: 15 }}>
          AI短视频创作 · 智能对话 · 知识库 · SOP工作流 — 零成本、全免费API驱动
        </p>
      </div>

      <div style={{ padding: "24px 40px 40px" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 20,
        }}>
          {cards.map((c) => (
            <Link key={c.href} href={c.href} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="card animate-fade-in" style={{
                padding: 28,
                borderTop: `3px solid ${c.color}`,
              }}>
                <div style={{ fontSize: 40, marginBottom: 16 }}>{c.icon}</div>
                <h3 style={{ fontSize: 18, fontWeight: 600, margin: "0 0 8px" }}>{c.title}</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: 13, margin: 0, lineHeight: 1.6 }}>{c.desc}</p>
              </div>
            </Link>
          ))}
        </div>

        <div className="glass" style={{
          marginTop: 28, padding: "20px 24px",
          display: "flex", alignItems: "center", gap: 16,
        }}>
          <span style={{
            width: 10, height: 10, borderRadius: "50%",
            background: status ? "var(--success)" : "var(--danger)",
            boxShadow: status ? "0 0 12px rgba(34,197,94,0.4)" : "none",
          }}/>
          <span style={{ fontSize: 14 }}>
            API: {status ? `✅ 正常 v${status.version}` : "❌ 未连接 — 请启动 python -m yuling.main"}
          </span>
        </div>
      </div>
    </div>
  );
}
