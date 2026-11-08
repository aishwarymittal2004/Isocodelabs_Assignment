import { createFileRoute, Link } from "@tanstack/react-router";
import { SiteHeader, SiteFooter, DemoNote } from "@/components/site";
import { projects, images } from "@/lib/mock-data";
import { sitepilotApi, backendProjectId, absoluteMediaUrl, type ApiProject } from "@/lib/sitepilot-api";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SitePilot AI — Find your home in Ahmedabad, at your pace" },
      { name: "description", content: "Explore verified 2 & 3 BHK homes, ask an AI assistant, and book a site visit only when you're ready." },
      { property: "og:title", content: "SitePilot AI — Homes in Ahmedabad" },
      { property: "og:description", content: "Verified project facts, a calm AI assistant and simple site-visit booking." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Home,
});

function Home() {
  const [published,setPublished]=useState<ApiProject[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState(false);
  useEffect(()=>{sitepilotApi.projects().then(setPublished).catch(()=>setError(true)).finally(()=>setLoading(false));},[]);
  return (
    <div>
      <section className="relative min-h-[92vh] overflow-hidden">
        <img src={images.hero} alt="Residential tower and landscaped courtyard at sunset" width={1920} height={1088} className="absolute inset-0 size-full object-cover" />
        <div className="hero-scrim absolute inset-0" />
        <SiteHeader overlay />
        <div className="relative z-10 mx-auto flex min-h-[92vh] max-w-7xl flex-col justify-end px-5 pb-16 md:px-8 md:pb-24">
          <p className="eyebrow mb-5 !text-primary-foreground/80">Residential projects · Review facts at your pace</p>
          <h1 className="max-w-4xl text-5xl leading-[0.95] text-primary-foreground md:text-8xl">Find a home that fits, in your own time.</h1>
          <p className="mt-6 max-w-xl text-lg text-primary-foreground/85">Explore published projects, ask about approved details, and request a visit without pressure. Images and some sample descriptions are illustrative.</p>
          <div className="mt-10 flex flex-wrap gap-3">
            <a href="#projects" className="btn btn-light">Explore projects</a>
            <Link to="/chat" className="btn btn-outline-light">Ask the AI assistant</Link>
          </div>
        </div>
      </section>

      <section id="projects" className="mx-auto max-w-7xl scroll-mt-8 px-5 pt-24 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Current projects</p>
            <h2 className="mt-3 text-4xl md:text-5xl">Explore published projects.</h2>
          </div>
          <DemoNote />
        </div>
        {loading&&<p role="status" className="mt-8">Loading published projects…</p>}
        {error&&<p role="alert" className="mt-8">Projects cannot be loaded. Check that SitePilot's API is available.</p>}
        {!loading&&!error&&published.length===0&&<p className="mt-8">No projects are published yet.</p>}
        <div className="mt-12 grid gap-8 md:grid-cols-2">
          {published.map((item)=>{
            const original=projects.find(p=>backendProjectId(p.id)===item.id);
            return <Link key={item.id} to="/projects/$id" params={{id:item.id}} className="group block">
              <div className="overflow-hidden rounded-[2rem]">
                {item.cover_image_url?<img src={absoluteMediaUrl(item.cover_image_url)} alt={`${item.name} — approved project photograph`} loading="lazy" className="aspect-[4/3] w-full object-cover transition duration-700 group-hover:scale-[1.03]"/>:original?<img src={original.image} alt="Illustrative residential architecture — not an actual project photograph" loading="lazy" className="aspect-[4/3] w-full object-cover transition duration-700 group-hover:scale-[1.03]"/>:<div className="grid aspect-[4/3] place-items-center bg-secondary text-muted-foreground">Project photo coming soon</div>}
              </div>
              <div className="mt-5"><h3 className="text-3xl">{item.name}</h3><p className="mt-2 text-muted-foreground">{item.city}</p><p className="mt-2 text-sm text-muted-foreground">{item.cover_image_url?'Project photograph published by the sales team.':'Review verified details before making a decision. Images are illustrative.'}</p></div>
            </Link>;
          })}
        </div>
      </section>

      <section className="mx-auto mt-28 grid max-w-7xl items-center gap-12 px-5 md:grid-cols-2 md:px-8">
        <img src={images.interior} alt="Sample apartment living room" loading="lazy" width={1280} height={960} className="aspect-[4/3] w-full rounded-[2rem] object-cover" />
        <div>
          <p className="eyebrow">How SitePilot helps</p>
          <h2 className="mt-3 text-4xl md:text-5xl">Answers you can trust. Decisions you control.</h2>
          <ul className="mt-8 space-y-6">
            {[
              ["Approved facts only", "The assistant answers from developer-approved information and says so when it doesn't know."],
              ["Your concerns, your words", "Mention a worry — a loan, a timeline — and get relevant information, not a sales push."],
              ["A person when you want one", "Hand over to a sales executive at any point, with context so you don't repeat yourself."],
            ].map(([t, d]) => (
              <li key={t} className="border-t border-border pt-5">
                <p className="font-semibold">{t}</p>
                <p className="mt-1 text-muted-foreground">{d}</p>
              </li>
            ))}
          </ul>
          <Link to="/chat" className="btn btn-primary mt-8">Start a conversation</Link>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}
