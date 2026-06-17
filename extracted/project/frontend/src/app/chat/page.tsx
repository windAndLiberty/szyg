"use client";

import { useState, useRef, useEffect } from "react";
import { chatCompletion } from "@/lib/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([
    { role: "assistant", content: "你好！我是域灵 AI 助手。我基于 OpenRouter 免费模型驱动，可以帮你回答问题、创作内容、分析数据。有什么我可以帮你的？" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streaming]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);

    try {
      const body = await chatCompletion("openrouter/free", [
        ...messages.filter((m) => m.content),
        { role: "user", content: text },
      ]);
      const content = body.choices?.[0]?.message?.content || "(empty response)";
      setMessages((m) => [...m, { role: "assistant", content }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "❌ API 连接失败，请检查后端服务" }]);
    }
    setLoading(false);
  }

  async function sendStream() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);
    setStreaming("");

    try {
      const sBody = await chatCompletion("openrouter/free", [
        ...messages.filter((m) => m.content),
        { role: "user", content: text },
      ], true);
      if (!sBody) throw new Error("no stream");

      const reader = sBody.getReader();
      const decoder = new TextDecoder();
      let full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((l) => l.startsWith("data: ") && !l.includes("[DONE]"));
        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6));
            const delta = data.choices?.[0]?.delta?.content || "";
            full += delta;
            setStreaming(full);
          } catch {}
        }
      }
      setMessages((m) => [...m, { role: "assistant", content: full }]);
      setStreaming("");
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "❌ 流式连接失败，请重试" }]);
      setStreaming("");
    }
    setLoading(false);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <div style={{ padding: "20px 40px", borderBottom: "1px solid var(--border)" }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>💬 智能对话</h2>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "24px 40px" }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            marginBottom: 16,
          }}>
            <div style={{
              maxWidth: "75%", padding: "14px 18px", borderRadius: 16,
              fontSize: 14, lineHeight: 1.7,
              background: m.role === "user"
                ? "linear-gradient(135deg, #6366f1, #8b5cf6)"
                : "var(--surface-card)",
              color: m.role === "user" ? "#fff" : "var(--text-primary)",
              border: m.role === "assistant" ? "1px solid var(--border)" : "none",
              animation: "fadeIn 0.3s ease-out",
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {streaming && (
          <div style={{ display: "flex", marginBottom: 16 }}>
            <div style={{
              maxWidth: "75%", padding: "14px 18px", borderRadius: 16,
              fontSize: 14, background: "var(--surface-card)",
              border: "1px solid var(--border)",
            }}>
              {streaming}<span style={{ color: "var(--primary)" }}>▍</span>
            </div>
          </div>
        )}
        {loading && !streaming && (
          <div style={{ display: "flex", gap: 8, padding: 16 }}>
            <div className="shimmer" style={{ width: 200, height: 16, borderRadius: 8 }}/>
            <div className="shimmer" style={{ width: 120, height: 16, borderRadius: 8 }}/>
          </div>
        )}
        <div ref={bottom}/>
      </div>

      <div style={{ padding: "16px 40px 24px", borderTop: "1px solid var(--border)" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendStream(); } }}
            placeholder="输入消息... (Enter 发送)"
            style={{
              flex: 1, padding: "12px 16px", borderRadius: 12,
              background: "var(--surface-card)", border: "1px solid var(--border)",
              color: "var(--text-primary)", fontSize: 14, outline: "none",
            }}
          />
          <button onClick={sendStream} disabled={loading} className="btn btn-primary" style={{ padding: "12px 24px" }}>
            {loading ? "..." : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
}
