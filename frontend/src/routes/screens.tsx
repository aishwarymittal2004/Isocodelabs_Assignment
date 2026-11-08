import { createFileRoute, Link } from "@tanstack/react-router";
import { SiteHeader } from "@/components/site";

export const Route = createFileRoute("/screens")({
  head: () => ({
    meta: [
      { title: "Screen inventory & flows — SitePilot AI" },
      { name: "description", content: "All buyer (B1–B6) and sales (S1–S6) screens and the key user journeys." },
      { property: "og:title", content: "SitePilot AI screen inventory" },
      { property: "og:description", content: "Buyer and sales workspace screens with user journeys." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Screens,
});

const buyer = [
  ["B1", "Home / discovery", "/"],
  ["B2", "Project details", "/projects/aranya"],
  ["B3", "AI conversation", "/chat"],
  ["B4", "Hesitation handling (in chat)", "/chat"],
  ["B5", "Site-visit booking", "/book"],
  ["B6", "Booking confirmation", "/booking/confirmed"],
] as const;
const sales = [
  ["S1", "Dashboard", "/sales"],
  ["S2", "Lead management", "/sales/leads"],
  ["S3", "Lead detail & hesitation summary", "/sales/leads/L-2041"],
  ["S4", "Visit management", "/sales/visits"],
  ["S5", "Project facts & slots", "/sales/admin"],
  ["S6", "Source analytics", "/sales/analytics"],
] as const;
const journeys = [
  "Explore project → Ask AI → Mention loan concern → Continue at my own pace",
  "Explore project → Book visit → Pick open slot → Confirm",
  "AI chat → Talk to a person → Executive sees handoff summary (S3)",
  "Open lead → Review concern evidence → View booking → Record outcome (S4)",
  "Edit project fact → Submit for review → Approve (S5)",
];

function Screens() {
  return (
    <div>
      <SiteHeader />
      <div className="mx-auto max-w-6xl px-5 py-14 md:px-8">
        <p className="eyebrow">Prototype map</p>
        <h1 className="mt-3 text-5xl">Screens & journeys</h1>
        <div className="mt-12 grid gap-10 md:grid-cols-2">
          {[["Buyer experience", buyer], ["Sales workspace", sales]].map(([title, list]) => (
            <section key={title as string}>
              <h2 className="text-2xl">{title as string}</h2>
              <ul className="mt-4 divide-y divide-border card-surface">
                {(list as typeof buyer).map(([id, name, to]) => (
                  <li key={id}><a href={to} className="flex items-center gap-4 px-5 py-4 hover:bg-secondary"><span className="font-mono text-xs text-accent">{id}</span><span className="flex-1">{name}</span><span aria-hidden>→</span></a></li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <h2 className="mt-14 text-2xl">Core journeys</h2>
        <ol className="mt-4 space-y-3">
          {journeys.map((j, i) => <li key={j} className="card-surface px-5 py-4 text-sm"><span className="mr-3 font-mono text-accent">J{i + 1}</span>{j}</li>)}
        </ol>
        <Link to="/" className="btn btn-primary mt-10">Start at home</Link>
      </div>
    </div>
  );
}
