const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const url = `${BACKEND}/${path.join("/")}${req.url.includes("?") ? "?" + req.url.split("?")[1] : ""}`;
  const res = await fetch(url, { headers: { "Content-Type": "application/json" } });
  return new Response(await res.text(), { status: res.status, headers: { "Content-Type": "application/json" } });
}

export async function POST(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const body = await req.text();
  const res = await fetch(`${BACKEND}/${path.join("/")}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body,
  });
  return new Response(await res.text(), { status: res.status, headers: { "Content-Type": "application/json" } });
}
