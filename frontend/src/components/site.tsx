import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { sitepilotApi } from "@/lib/sitepilot-api";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className={`flex items-center gap-2 font-display text-xl ${light ? "text-primary-foreground" : "text-foreground"}`}>
      <span className="grid size-8 place-items-center rounded-full bg-primary text-sm text-primary-foreground">S</span>
      SitePilot<span className="text-accent">.</span>
    </Link>
  );
}

export function SiteHeader({ overlay = false }: { overlay?: boolean }) {
  const link = overlay ? "text-primary-foreground/90 hover:text-primary-foreground" : "text-muted-foreground hover:text-foreground";
  return (
    <header className={`${overlay ? "absolute inset-x-0 top-0 z-20" : "border-b border-border bg-background"}`}>
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 md:px-8">
        <Logo light={overlay} />
        <nav className="hidden items-center gap-8 text-sm font-medium md:flex">
          <Link to="/" hash="projects" className={link}>Projects</Link>
          <Link to="/chat" className={link}>Ask AI</Link>
          <Link to="/sales" className={link}>Sales workspace</Link>
          <Link to="/buyer/visits" className={link}>My visits / Sign in</Link>
        </nav>
        <div className="flex items-center gap-2"><Link to="/buyer/visits" className={`text-sm font-semibold ${overlay ? "text-primary-foreground" : "text-foreground"}`}>Sign in</Link><Link to="/book" className={`btn ${overlay ? "btn-light" : "btn-primary"}`}>Book a visit</Link></div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const [contact,setContact]=useState<{phone:string|null;email:string|null}>({phone:null,email:null});
  useEffect(()=>{let live=true;sitepilotApi.contact().then(c=>{if(live)setContact(c)}).catch(()=>{});return()=>{live=false}},[]);
  return (
    <footer className="mt-24 border-t border-border bg-card">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-10 text-sm md:flex-row md:items-center md:justify-between md:px-8">
        <div><Logo/><p className="mt-3 text-xs text-muted-foreground">Explore at your pace. Ask for a person when you need one.</p></div>
        <div className="space-y-1 text-muted-foreground md:text-right">
          <p className="font-semibold text-foreground">Contact SitePilot</p>
          {contact.phone&&<p><a className="underline underline-offset-2 hover:text-foreground" href={`tel:${contact.phone}`}>{contact.phone}</a></p>}
          {contact.email&&<p><a className="underline underline-offset-2 hover:text-foreground" href={`mailto:${contact.email}`}>{contact.email}</a></p>}
          {!contact.phone&&!contact.email&&<p>Contact details will appear once approved by the sales team.</p>}
          <Link to="/chat" className="inline-block pt-1 font-medium text-primary underline underline-offset-2">Send an enquiry</Link>
        </div>
      </div>
    </footer>
  );
}

export function DemoNote({ children }: { children?: ReactNode }) {
  return (
    <p className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
      <span className="size-1.5 rounded-full bg-accent" aria-hidden />
      {children ?? "Illustrative data"}
    </p>
  );
}

const tone: Record<string, string> = {
  green: "bg-primary/10 text-primary border-primary/20",
  copper: "bg-accent/10 text-accent border-accent/30",
  amber: "bg-warning/15 text-foreground border-warning/40",
  red: "bg-destructive/10 text-destructive border-destructive/30",
  gray: "bg-muted text-muted-foreground border-border",
};
export function Badge({ children, t = "gray", icon }: { children: ReactNode; t?: keyof typeof tone; icon?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tone[t]}`}>
      {icon && <span aria-hidden>{icon}</span>}
      {children}
    </span>
  );
}

export const statusTone = (s: string): keyof typeof tone =>
  ({ New: "copper", Contacted: "gray", "Handoff requested": "amber", "Visit booked": "green", Visited: "green", "Not interested": "gray",
    Upcoming: "copper", Confirmed: "green", Cancelled: "red", Attended: "green", "No-show": "red" } as Record<string, keyof typeof tone>)[s] ?? "gray";
export const statusIcon = (s: string) =>
  ({ Confirmed: "✓", Attended: "✓", Visited: "✓", Cancelled: "✕", "No-show": "✕", "Handoff requested": "!", New: "•", Upcoming: "◷" } as Record<string, string>)[s];
