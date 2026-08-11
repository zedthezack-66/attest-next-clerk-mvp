"use client";
import { FormEvent, useState } from "react";
import { api } from "../../lib/api-client";

export default function Login() {
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const data = await api<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      localStorage.setItem("attest_token", data.access_token);
      location.href = "/";
    } catch {
      setError("Invalid email or password");
    }
  }
  return <main className="mx-auto max-w-sm px-6 py-16">
    <h1 className="text-2xl font-semibold">Hiring Manager Login</h1>
    <form onSubmit={submit} className="mt-6 grid gap-3">
      <input name="email" type="email" defaultValue="manager@attest.local" className="rounded border border-stone-300 p-3" />
      <input name="password" type="password" defaultValue="password123" className="rounded border border-stone-300 p-3" />
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button className="rounded bg-slate-900 px-4 py-3 text-white">Sign in</button>
    </form>
  </main>;
}

