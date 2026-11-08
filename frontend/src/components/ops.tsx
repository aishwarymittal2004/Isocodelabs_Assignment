import type { ReactNode } from "react";

export function PageTitle({ id, title, children }: { id: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><p className="font-mono text-xs text-accent">{id}</p><h1 className="text-3xl">{title}</h1></div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

export function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card-surface p-5">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-2 font-display text-3xl tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="card-surface">
      <div className="flex items-center justify-between border-b border-border px-5 py-3"><h2 className="font-sans text-sm font-bold tracking-normal">{title}</h2>{action}</div>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Bar({ value, max, label }: { value: number; max: number; label?: string }) {
  return (
    <div className="h-2.5 w-full rounded-full bg-muted" role="img" aria-label={label ?? `${value} of ${max}`}>
      <div className="h-full rounded-full bg-primary" style={{ width: `${(value / max) * 100}%` }} />
    </div>
  );
}
