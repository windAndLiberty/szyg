"use client";

import { useState } from "react";

export default function KnowledgePage() {
  const [files, setFiles] = useState<{ name: string; chunks: number }[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ content: string; source: string }[]>([]);
  const [dragging, setDragging] = useState(false);

  async function uploadText(text: string, name: string) {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/knowledge/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source: name }),
    });
    const data = await res.json();
    setFiles((f) => [...f, { name, chunks: data.chunks || 0 }]);
  }

  async function search() {
    if (!query.trim()) return;
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/knowledge/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    setResults(data.results || []);
  }

  return (
    <div className="animate-fade-in">
      <div style={{ padding: "32px 40px 0" }}>
        <h2 style={{ fontSize: 22, margin: 0 }}>📚 知识库</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: 14 }}>
          上传文档，AI自动学习分块，检索时精准返回相关上下文
        </p>
      </div>

      <div style={{ padding: "24px 40px 40px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <div
            className="card"
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault(); setDragging(false);
              const file = e.dataTransfer.files[0];
              if (file) {
                const reader = new FileReader();
                reader.onload = (ev) => uploadText(ev.target?.result as string, file.name);
                reader.readAsText(file);
              }
            }}
            style={{ border: `2px dashed ${dragging ? "var(--primary)" : "var(--border)"}`, padding: 32, textAlign: "center" }}
          >
            <div style={{ fontSize: 36, marginBottom: 8 }}>📁</div>
            <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>拖放文件到此处上传</p>
            <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>支持 .txt .md .json</p>
          </div>

          {files.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4 style={{ fontSize: 14, marginBottom: 8 }}>已上传</h4>
              {files.map((f, i) => (
                <div key={i} style={{ padding: "8px 12px", borderRadius: 8, background: "var(--surface-card)", marginBottom: 6, fontSize: 13, display: "flex", justifyContent: "space-between" }}>
                  <span>{f.name}</span>
                  <span style={{ color: "var(--primary)" }}>{f.chunks} 块</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="card">
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              <input
                value={query} onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                placeholder="搜索知识库..."
                style={{ flex: 1 }}
              />
              <button onClick={search} className="btn btn-primary btn-sm">搜索</button>
            </div>

            {results.map((r, i) => (
              <div key={i} style={{ padding: 12, borderRadius: 10, background: "var(--surface)", marginBottom: 8, fontSize: 13, lineHeight: 1.6 }}>
                <div>{r.content.slice(0, 300)}{r.content.length > 300 ? "..." : ""}</div>
                <div style={{ color: "var(--primary)", fontSize: 11, marginTop: 6 }}>来源: {r.source}</div>
              </div>
            ))}
            {results.length === 0 && query && (
              <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>无匹配结果，请先上传文档</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
