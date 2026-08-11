const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function token() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("attest_token") ?? "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", headers.get("Content-Type") ?? "application/json");
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetch(`${API}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

