import {useEffect,useState} from 'react';
import {sitepilotApi, ticketApi, type ApiProject, type BuyerTicketSummary} from '@/lib/sitepilot-api';
export function BuyerTicketPanel({token,onStatusChange}:{token:string;onStatusChange?:(state:string)=>void}){
 const [ticket,setTicket]=useState<BuyerTicketSummary|null>(null);
 const [projects,setProjects]=useState<ApiProject[]>([]);
 const [chosen,setChosen]=useState('');
 const [error,setError]=useState('');
 const [facts,setFacts]=useState<Array<{id:string;name:string;facts:Record<string,string>}>>([]);
 const [showFacts,setShowFacts]=useState(false);
 const refresh=()=>{ticketApi.current(token).then(t=>{setTicket(t);onStatusChange?.(t.status)}).catch(e=>setError(String(e)))};
 useEffect(()=>{refresh();sitepilotApi.projects().then(setProjects).catch(()=>{});const id=setInterval(refresh,5000);return()=>clearInterval(id)},[token]);
 const addProject=async()=>{if(!chosen)return;setError('');try{setTicket(await ticketApi.addProject(token,chosen));setChosen('')}catch(e){setError(String(e))}};
 const download=async()=>{try{await ticketApi.download(token)}catch(e){setError(String(e))}};
 const compare=async()=>{try{const result=await ticketApi.projectFacts(token);setFacts(result.projects);setShowFacts(true)}catch(e){setError(String(e))}};
 return <section className="rounded-2xl border bg-card p-4 text-sm" aria-label="Enquiry ticket">
 <div className="flex flex-wrap items-center justify-between gap-2"><strong>Enquiry {ticket?.reference??'loading…'}</strong><span className="text-xs text-muted-foreground">{ticket?.status?.replaceAll('_',' ')??''}</span></div>
 {ticket?.owner?<p className="mt-2">Assigned salesperson: <strong>{ticket.owner.name}</strong> · <a className="underline" href={`mailto:${ticket.owner.email}`}>{ticket.owner.email}</a></p>:<p className="mt-2 text-muted-foreground">One ticket covers your entire property search. Any human request stays in this ticket.</p>}
 {ticket?.status==='accepted'&&<p className="mt-2 text-primary">A salesperson has accepted responsibility. AI replies are off; your new messages go to the assigned person.</p>}
 <div className="mt-3 flex flex-wrap items-center gap-2"><button type="button" className="btn btn-ghost" onClick={download}>Download ticket</button><button type="button" className="btn btn-ghost" onClick={refresh}>Refresh status</button><button type="button" className="btn btn-ghost" onClick={compare}>Verified project comparison</button></div>
 <div className="mt-3 flex flex-wrap gap-2"><label className="sr-only" htmlFor="ticket-other-project">Add a project to this ticket</label><select id="ticket-other-project" value={chosen} onChange={e=>setChosen(e.target.value)} className="rounded-lg border bg-background p-2"><option value="">Compare another project</option>{projects.filter(p=>!ticket?.project_ids.includes(p.id)).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><button type="button" className="btn btn-ghost" disabled={!chosen} onClick={addProject}>Add to same ticket</button></div>
 {ticket?.project_ids.length?<p className="mt-2 text-xs text-muted-foreground">Projects on ticket: {ticket.project_ids.map(id=>projects.find(p=>p.id===id)?.name??id).join(', ')}</p>:null}
 {showFacts&&<div className="mt-3 space-y-3 border-t pt-3">{facts.map(p=><div key={p.id}><h3 className="font-semibold">{p.name}</h3>{Object.keys(p.facts).length===0?<p className="text-muted-foreground">No approved facts have been published for this project.</p>:<ul className="ml-5 list-disc space-y-1">{Object.entries(p.facts).slice(0,12).map(([key,value])=><li key={key}><strong>{key.replaceAll('_',' ')}:</strong> {value}</li>)}</ul>}</div>)}</div>}
 {error&&<p role="alert" className="mt-2 text-red-700">{error}</p>}
 </section>;
}
