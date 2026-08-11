import clsx from "clsx";
import type { ReactNode } from "react";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "amber" }) {
  return <span className={clsx("inline-flex rounded px-2 py-1 text-xs font-medium", tone === "green" && "bg-emerald-100 text-emerald-800", tone === "amber" && "bg-amber-100 text-amber-800", tone === "neutral" && "bg-slate-100 text-slate-700")}>{children}</span>;
}

