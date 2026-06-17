"use client";

import { useState } from "react";

export default function VideoPage() {
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const steps = [
    { label: "AI 脚本生成", desc: "OpenRouter 根据主题创作视频脚本" },
    { label: "封面图生成", desc: "DashScope qwen-image-plus AI绘画" },
    { label: "配音生成", desc: "edge-tts 免费微软中文语音合成" },
    { label: "视频合成", desc: "FFmpeg 专业级视频编码输出" },
  ];

  return (
    <div className="animate-fade-in">
      <div style={{ padding: "32px 40px 0" }}>
        <h2 style={{ fontSize: 22, margin: 0 }}>🎬 视频创作</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: 14 }}>
          输入主题，AI 自动完成脚本 → 封面 → 配音 → 合成全流程
        </p>
      </div>

      <div style={{ padding: "24px 40px 40px" }}>
        {/* 步骤 */}
        <div style={{ display: "flex", gap: 16, marginBottom: 28 }}>
          {steps.map((s, i) => (
            <div key={i} className="glass" style={{
              flex: 1, padding: "16px 20px", textAlign: "center",
              borderColor: loading ? "var(--primary)" : "var(--border)",
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: loading ? "var(--primary)" : "var(--surface-hover)",
                color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 8px", fontSize: 14, fontWeight: 600,
              }}>{i + 1}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{s.label}</div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>{s.desc}</div>
            </div>
          ))}
        </div>

        <div className="card" style={{ maxWidth: 600 }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6, display: "block" }}>视频主题</label>
            <input
              value={topic} onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：AI如何改变短视频创作"
            />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6, display: "block" }}>时长(秒)</label>
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} style={{ width: 120 }}>
              {[15, 30, 45, 60, 90, 120].map((d) => (
                <option key={d} value={d}>{d}s</option>
              ))}
            </select>
          </div>
          <button
            disabled={!topic || loading}
            className="btn btn-primary"
            onClick={async () => {
              setLoading(true); setResult(null);
              try {
                const res = await fetch(`http://localhost:8000/api/video/create?topic=${encodeURIComponent(topic)}&duration=${duration}`, { method: "POST" });
                const data = await res.json();
                setResult(data.video || JSON.stringify(data));
              } catch { setResult("❌ 后端未运行。请用命令行执行：python -m yuling.pipelines.video_creator"); }
              setLoading(false);
            }}
          >
            {loading ? "⏳ AI 创作中..." : "🚀 开始创作"}
          </button>
          {result && (
            <div style={{ marginTop: 20, padding: 16, borderRadius: 10, background: "var(--surface)", fontSize: 13 }}>
              {result.startsWith("❌") ? result : `✅ 视频已生成: ${result}`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
