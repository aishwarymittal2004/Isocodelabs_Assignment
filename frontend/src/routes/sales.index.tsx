import {createFileRoute,Link} from '@tanstack/react-router';
import {PageTitle,Kpi,Panel,Bar} from '@/components/ops';
import {salesApi} from '@/lib/sitepilot-api';
import {useSalesData,DataState} from '@/lib/use-sales-data';
export const Route=createFileRoute('/sales/')({component:Dashboard});
function Dashboard(){
 const {data,error,loading,reload}=useSalesData(salesApi.dashboard);
 const handoffs=useSalesData(salesApi.handoffs);
 if(!data)return <DataState loading={loading} error={error} retry={reload}/>;
 const max=Math.max(1,...data.sources.map(s=>s.leads));
 return <div><PageTitle id="S1" title="Sales overview"><div className="flex flex-wrap gap-2"><Link className="btn btn-ghost" to="/sales/admin">Add a project</Link><Link className="btn btn-primary" to="/sales/leads">Open leads</Link><Link className="btn btn-ghost" to="/sales/reviews">Daily AI review</Link></div></PageTitle>
 <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Kpi label="Leads this month" value={String(data.leads_this_month)} sub={`${data.leads_total} total records`}/><Kpi label="Median first AI reply" value={data.median_first_response_minutes===null?'Not measured':`${data.median_first_response_minutes} min`} sub={`${data.response_sample_size} AI conversations measured`}/><Kpi label="Visits booked" value={String(data.booked_visits)} sub="Non-cancelled bookings"/><Kpi label="No chat reply >48h" value={String(data.unreplied_over_48h)} sub="From persisted message timestamps"/></div>
 <div className="mt-6 grid gap-6 xl:grid-cols-2"><Panel title={`Pending human handoffs (${data.handoff_pending})`} action={<Link to="/sales/leads" className="text-sm text-primary">All leads</Link>}><div className="space-y-3">{handoffs.loading?<p>Loading…</p>:handoffs.error?<p role="alert">{handoffs.error}</p>:handoffs.data?.length?handoffs.data.map(l=><Link key={l.lead_id} to="/sales/leads/$id" params={{id:l.lead_id}} className="block border-b border-border pb-2 text-sm">{l.name} · {l.source} →</Link>):<p className="text-sm text-muted-foreground">No pending handoffs.</p>}</div></Panel><Panel title="Leads by source"><ul className="space-y-3">{data.sources.length?data.sources.map(s=><li key={s.source} className="grid grid-cols-[110px_1fr_48px] items-center gap-3 text-sm"><span>{s.source}</span><Bar value={s.leads} max={max}/><span className="text-right">{s.leads}</span></li>):<li className="text-sm text-muted-foreground">No lead data yet.</li>}</ul></Panel></div>
 <div className="mt-6"><Panel title="Visits attended"><p className="font-display text-3xl">{data.attended_visits}</p><Link to="/sales/visits" className="mt-3 inline-block text-sm text-primary">Manage visits →</Link></Panel></div></div>;
}
