import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { buyerSession, backendProjectId, sitepilotApi } from "@/lib/sitepilot-api";
import { SiteHeader, DemoNote } from "@/components/site";
import { getProject } from "@/lib/mock-data";

type Search = { project?: string; date?: string; time?: string; ref?: string };
export const Route = createFileRoute("/booking/confirmed")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    project: s.project as string | undefined, date: s.date as string | undefined, time: s.time as string | undefined, ref: s.ref as string | undefined,
  }),
  head: () => ({
    meta: [
      { title: "Visit confirmed — SitePilot AI" },
      { name: "description", content: "Your site visit booking details and next steps." },
      { property: "og:title", content: "Visit confirmed" },
      { property: "og:description", content: "Booking reference, date, time and location." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Confirmed,
});

function Confirmed() {
  const s = Route.useSearch();
  const p = getProject(s.project ?? "aranya");
  const projectId = backendProjectId(s.project ?? "aranya");
  const [cancelled, setCancelled] = useState(false);
  const [verified, setVerified] = useState(false);
  const [verifying, setVerifying] = useState(true);
  const [verifiedBooking, setVerifiedBooking] = useState<Awaited<ReturnType<typeof sitepilotApi.bookings>>[number] | null>(null);
  const [asking, setAsking] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const token = buyerSession.load(s.ref ?? "");
    if (!token || !s.ref) {setError("A booking reference and active buyer session are required.");setVerifying(false);return;}
    let active = true;
    sitepilotApi.bookings(token).then(rows => {
      if (!active) return;
      const found = rows.find(row => row.booking_id === s.ref && row.project_id === projectId);
      if (!found) setError("This booking cannot be verified for your session.");
      else {setVerified(true);setVerifiedBooking(found);setCancelled(found.status === 'cancelled');}
    }).catch(err => {if(active)setError(err instanceof Error?err.message:"Unable to verify booking");})
      .finally(()=>{if(active)setVerifying(false)});
    return ()=>{active=false};
  },[(p?.id??projectId),s.ref]);
  const cancelBooking = async () => {
    const token = buyerSession.load(s.ref ?? "");
    if (!token || !s.ref) { setError("Cannot verify this booking session. Please contact the sales team."); return; }
    setPending(true); setError("");
    try { const result = await sitepilotApi.cancel(s.ref, token); if(result.status === "cancelled") {setCancelled(true);setAsking(false);} }
    catch (err) {setError(err instanceof Error ? err.message : "Could not cancel the visit");}
    finally {setPending(false);}
  };
  if(verifying)return <div className="min-h-screen"><SiteHeader/><main role="status" className="mx-auto max-w-4xl p-10">Checking booking with the server…</main></div>;
  if(!verified)return <div className="min-h-screen"><SiteHeader/><main className="mx-auto max-w-4xl p-10"><h1 className="text-3xl">Booking not verified</h1><p role="alert" className="mt-4">{error || 'This appointment could not be confirmed.'}</p><Link to="/book" className="btn btn-primary mt-6">Check availability</Link></main></div>;
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <div className="mx-auto grid max-w-6xl gap-12 px-5 py-14 md:grid-cols-2 md:px-8">
        <div className="rise">
          <span className={`inline-flex size-14 items-center justify-center rounded-full text-2xl ${cancelled ? "bg-muted" : "bg-primary text-primary-foreground"}`} aria-hidden>{cancelled ? "✕" : "✓"}</span>
          <p className="eyebrow mt-6">{cancelled ? "Visit cancelled" : "Visit confirmed"}</p>
          <h1 className="mt-3 text-5xl md:text-6xl">{cancelled ? "Your visit has been cancelled." : "We'll see you soon."}</h1>
          <p className="mt-4 text-muted-foreground">{cancelled ? "No further messages will be sent about this visit. You're welcome to book again any time." : "Your booking was recorded by the SitePilot API. Automated SMS and WhatsApp reminders are not yet connected."}</p>

          {error && <p role="alert" className="mt-5 text-destructive">{error}</p>}
          <dl className="mt-10 card-surface divide-y divide-border">
            {[["Reference", s.ref ?? "—"], ["Project", (p?.name??"Your project")], ["Date", verifiedBooking ? new Date(verifiedBooking.starts_at).toLocaleDateString("en-IN",{timeZone:"Asia/Kolkata",dateStyle:"medium"}) : "—"], ["Time", verifiedBooking ? new Date(verifiedBooking.starts_at).toLocaleTimeString("en-IN",{timeZone:"Asia/Kolkata",timeStyle:"short"}) : "—"], ["Location", `Venue details pending confirmation, ${(p?.locality??"location pending")}`]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-5 py-4 text-sm"><dt className="text-muted-foreground">{k}</dt><dd className={`text-right font-semibold ${cancelled && k !== "Reference" ? "line-through opacity-60" : ""}`}>{v}</dd></div>
            ))}
          </dl>

          {!cancelled && (
            <>
              <h2 className="mt-10 text-2xl">What happens next</h2>
              <ol className="mt-4 space-y-3 text-sm">
                <li>1. Reminder delivery is not enabled in this demo.</li>
                <li>2. The sales team will confirm exact arrival instructions.</li>
                <li>3. Ask the sales team if you need to bring any documents.</li>
              </ol>
            </>
          )}

          <div className="mt-8 flex flex-wrap gap-3">
            {cancelled ? (
              <Link to="/book" search={{ project: (p?.id??projectId) }} className="btn btn-primary">Book again</Link>
            ) : asking ? (
              <div role="alertdialog" className="w-full rounded-2xl border border-border bg-card p-5">
                <p className="font-semibold">Cancel this visit?</p>
                <div className="mt-4 flex gap-3">
                  <button disabled={pending} onClick={cancelBooking} className="btn bg-destructive text-destructive-foreground">{pending ? "Cancelling…" : "Yes, cancel"}</button>
                  <button onClick={() => setAsking(false)} className="btn btn-ghost">Keep visit</button>
                </div>
              </div>
            ) : (
              <>
                <Link to="/book" search={{ project: (p?.id??projectId) }} className="btn btn-primary">Choose another visit time</Link>
                <button onClick={() => setAsking(true)} className="btn btn-ghost">Cancel visit</button>
                <Link to="/buyer/visits" className="btn btn-ghost">My visits / Sign in</Link>
              </>
            )}
          </div>
          <Link to="/buyer/visits" className="mt-5 inline-flex text-sm font-semibold underline">Manage this booking later by signing in</Link>
          <div className="mt-6"><DemoNote>Confirmed by backend · Notifications not connected</DemoNote></div>
        </div>
        {p?.image?<img src={p.image} alt={p.name} width={1280} height={960} className="aspect-[4/5] w-full rounded-[2rem] object-cover" />:<div className="grid aspect-[4/5] place-items-center rounded-3xl bg-secondary">Site visit details</div>}
      </div>
    </div>
  );
}
