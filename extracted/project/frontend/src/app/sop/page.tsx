"use client";

import { useState, useEffect } from "react";

export default function SOPPage() {
  const [sops, setSops] = useState<{ id: string; name: string; description: string; steps: { skill: string; description: string; on_failure: string }[] }[]>([]);
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/sop/list`).then(r => r.json()).then(d => setSops(d.sops || [])).catch(() => {});
  }, []);

  return (
    <div className="animate-fade-in">
      <div style={{ padding: "32px 40px 0", display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <h2 style={{ fontSize: 22, margin: 0 }}>📋 SOP 管理</h2>
          <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: 14 }}>
            标准操作流程 — 定义→存储→自动执行
          </p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)} className="btn btn-primary">
          {showAdd ? "取消" : "+ 新建 SOP"}
        </button>
      </div>

      <div style={{ padding: "24px 40px 40px" }}>
        {showAdd && (
          <div className="card animate-fade-in" style={{ marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16 }}>创建新 SOP</h3>
            <form onSubmit={async (e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const steps = [
                { skill: form.get("step1_skill") as string, description: form.get("step1_desc") as string, on_failure: "stop" },
                { skill: form.get("step2_skill") as string, description: form.get("step2_desc") as string, on_failure: "skip" },
                { skill: form.get("step3_skill") as string, description: form.get("step3_desc") as string, on_failure: "skip" },
              ].filter(s => s.skill);
              await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/sop/define`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: form.get("name"), description: form.get("desc"), steps }),
              });
              setShowAdd(false);
              const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/sop/list`).then(r => r.json());
              setSops(r.sops || []);
            }}>
              <div style={{ display: "grid", gap: 12 }}>
                <input name="name" placeholder="SOP 名称 (如: 短视频标准创作流程)" required />
                <input name="desc" placeholder="描述" />
                {[1, 2, 3].map(i => (
                  <div key={i} style={{ display: "flex", gap: 8 }}>
                    <input name={`step${i}_skill`} placeholder={`步骤${i}: 技能名`} style={{ flex: 1 }} />
                    <input name={`step${i}_desc`} placeholder="描述" style={{ flex: 2 }} />
                  </div>
                ))}
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: 16 }}>💾 保存</button>
            </form>
          </div>
        )}

        <div style={{ display: "grid", gap: 16 }}>
          {sops.map((sop) => (
            <div key={sop.id} className="card animate-fade-in" style={{ borderLeft: "3px solid var(--primary)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 16 }}>{sop.name}</h3>
                <span className="badge badge-info">{sop.steps.length} 步骤</span>
              </div>
              <p style={{ color: "var(--text-secondary)", fontSize: 13, margin: "0 0 12px" }}>{sop.description}</p>
              <div style={{ display: "flex", gap: 12 }}>
                {sop.steps.map((s, i) => (
                  <div key={i} style={{
                    flex: 1, padding: 10, borderRadius: 8, background: "var(--surface)",
                    fontSize: 12, textAlign: "center",
                  }}>
                    <div style={{ color: "var(--primary)", fontWeight: 600, marginBottom: 4 }}>Step {i + 1}</div>
                    <div style={{ color: "var(--text-primary)" }}>{s.skill}</div>
                    <div style={{ color: "var(--text-secondary)", fontSize: 11, marginTop: 2 }}>{s.on_failure === "stop" ? "失败停止" : "失败跳过"}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {sops.length === 0 && (
            <p style={{ color: "var(--text-secondary)", fontSize: 14, textAlign: "center", padding: 40 }}>
              暂未定义 SOP。点击「新建 SOP」创建你的第一个自动工作流。
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
