const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${BACKEND}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function chatCompletion(
  model: string,
  messages: { role: string; content: string }[],
  stream = false
) {
  if (stream) {
    const res = await fetch(`${BACKEND}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, stream: true }),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.body;
  }
  return apiFetch("/v1/chat/completions", {
    method: "POST",
    body: JSON.stringify({ model, messages, stream: false }),
  });
}

export async function healthCheck() {
  return apiFetch("/health");
}

export async function listModels() {
  return apiFetch("/v1/models");
}
