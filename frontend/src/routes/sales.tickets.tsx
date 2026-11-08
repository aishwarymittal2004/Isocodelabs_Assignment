import {createFileRoute} from '@tanstack/react-router';
import {useEffect,useState} from 'react';
import {useSalesAuth} from '@/lib/sales-auth';
import {ticketApi,type BuyerTicketSummary,type TicketHistoryEntry} from '@/lib/sitepilot-api';
export const Route=createFileRoute('/sales/tickets')({component:TicketsScreen});
function TicketsScreen(){
 const {token}=useSalesAuth();
 const [queue,setQueue]=useState<BuyerTicketSummary[]>([]),[mine,setMine]=useState<BuyerTicketSummary[]>([]);
 const [current,setCurrent]=useState<BuyerTicketSummary|null>(null),[history,setHistory]=useState<TicketHistoryEntry[]>([]);
 const [draft,setDraft]=useState(''),[note,setNote]=useState(''),[error,setError]=useState('');
 const reload=async()=>{try{const [q,m]=await Promise.all([ticketApi.queue(token),ticketApi.mine(token)]);setQueue(q);setMine(m)}catch(e){setError(String(e))}};
 useEffect(()=>{void reload();const t=setInterval(()=>void reload(),5000);return()=>clearInterval(t)},[token]);
 const open=async(t:BuyerTicketSummary)=>{try{const r=await ticketApi.salesDetail(token,t.id);setCurrent(r.ticket);setHistory(r.history)}catch(e){setError(String(e))}};
 const accept=async(t:BuyerTicketSummary)=>{try{await ticketApi.accept(token,t.id);await reload();await open(t)}catch(e){setError(String(e));await reload()}};
 const send=async()=>{if(!current||!draft.trim())return;try{await ticketApi.salesMessage(token,current.id,draft);setDraft('');await open(current)}catch(e){setError(String(e))}};
 const resolve=async()=>{if(!current||!note.trim())return;try{await ticketApi.resolve(token,current.id,note);setNote('');await reload();await open(current)}catch(e){setError(String(e))}};
 return <div className="space-y-6"><h1 className="font-display text-3xl">Ticket ownership</h1><p className="text-sm text-muted-foreground">First salesperson to accept owns the full buyer enquiry. No parallel acceptance; the AI stops when claimed.</p>
 {error&&<p role="alert" className="rounded-lg border p-3 text-red-700">{error}</p>}
 <div className="grid gap-5 lg:grid-cols-2"><section className="rounded-2xl border bg-card p-5"><h2 className="mb-4 font-semibold">Awaiting acceptance ({queue.length})</h2>{queue.map(t=><div key={t.id} className="mb-3 flex items-center justify-between gap-2 border-b pb-2"><span>{t.reference} · {t.project_ids.length} projects</span><button className="btn btn-primary" type="button" onClick={()=>accept(t)}>Accept</button></div>)}</section><section className="rounded-2xl border bg-card p-5"><h2 className="mb-4 font-semibold">My tickets ({mine.length})</h2>{mine.map(t=><button key={t.id} onClick={()=>open(t)} className="mb-2 block w-full rounded-lg border p-2 text-left">{t.reference} · {t.status}</button>)}</section></div>
 {current&&<section className="rounded-2xl border bg-card p-5"><h2 className="font-semibold">{current.reference} · {current.status}</h2><p className="mt-2 text-sm">Projects: {current.project_ids.join(', ')}</p><p className="mt-1 text-sm">Buyer phone: {current.buyer_phone??'Not shared — buyer contact consent required'}</p><div className="mt-4 max-h-96 space-y-2 overflow-y-auto border-t pt-3">{history.map(e=><div key={e.id} className="rounded-lg bg-secondary p-3 text-sm"><small className="text-muted-foreground">{e.type==='message'?e.speaker:e.kind} · {new Date(e.at).toLocaleString()}</small><p className="whitespace-pre-wrap">{e.text}</p></div>)}</div>
 {current.status==='accepted'&&<><div className="mt-4 flex gap-2"><input aria-label="Reply to buyer" value={draft} onChange={e=>setDraft(e.target.value)} className="min-w-0 flex-1 rounded-lg border p-3" placeholder="Reply in this ticket"/><button className="btn btn-primary" type="button" onClick={send}>Send</button></div><div className="mt-3 flex gap-2"><input aria-label="Resolution note" value={note} onChange={e=>setNote(e.target.value)} className="min-w-0 flex-1 rounded-lg border p-3" placeholder="Resolution note"/><button className="btn btn-ghost" type="button" onClick={resolve}>Resolve</button></div></>}
 </section>}</div>;
}
