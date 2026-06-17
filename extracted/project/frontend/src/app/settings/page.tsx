"use client";

import { useState, useEffect } from "react";

export default function SettingsPage() {
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/config`).then(r => r.json()).then(setConfig).catch(() => {});
  }, []);

  return (
    <div className="animate-fade-in">
      <div style={{ padding: "32px 40px 0" }}>
        <h2 style={{ fontSize: 22, margin: 0 }}>⚙️ 系统设置</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: 14 }}>
          管理 API Key、后端配置。敏感信息通过环境变量注入，config.yaml 中使用 ${"{VAR}"} 占位
        </p>
      </div>

      <div style={{ padding: "24px 40px 40px" }}>
        <div className="grid-cards" style={{ display: "grid", gap: 20 }}>
          <Section title="LLM 后端" icon="🧠">
            <Row label="OpenRouter API Key" value={String(config?.llm?.openrouter?.api_key || "").slice(0, 12) + "..."} />
            <Row label="ModelScope API Key" value={String(config?.llm?.modelscope?.api_key || "").slice(0, 12) + "..." || "未设置"} />
            <Row label="Ollama" value={String(config?.llm?.ollama?.base_url || "http://localhost:11434")} />
            <Row label="默认后端" value={String(config?.llm?.default_backend || "openrouter")} />
          </Section>

          <Section title="图像生成" icon="🎨">
            <Row label="DashScope API Key" value={String(config?.image?.dashscope?.api_key || "").slice(0, 12) + "..."} />
            <Row label="模型" value={String(config?.image?.dashscope?.model || "qwen-image-plus")} />
          </Section>

          <Section title="语音合成" icon="🎙️">
            <Row label="TTS 引擎" value="edge-tts (微软免费)" />
            <Row label="默认语音" value={String(config?.tts?.edge_tts?.voice || "zh-CN-XiaoxiaoNeural")} />
          </Section>

          <Section title="视频处理" icon="🎬">
            <Row label="FFmpeg" value={String(config?.video?.ffmpeg_path || "ffmpeg")} />
            <Row label="输出目录" value={String(config?.video?.output_dir || "./data/output")} />
          </Section>
        </div>

        {saved && (
          <div style={{ marginTop: 20, padding: 12, borderRadius: 8, background: "rgba(34,197,94,0.1)", color: "var(--success)", fontSize: 13 }}>
            ✅ 配置已保存。请重启后端服务生效。
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 style={{ fontSize: 16, margin: "0 0 16px", fontWeight: 600 }}>{icon} {title}</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--text-primary)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {value || "—"}
      </span>
    </div>
  );
}
