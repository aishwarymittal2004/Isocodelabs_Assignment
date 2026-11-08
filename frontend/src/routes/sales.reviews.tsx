import {createFileRoute, Link} from '@tanstack/react-router';
import {useState} from 'react';
import {PageTitle,Panel} from '@/components/ops';
import {useSalesAuth} from '@/lib/sales-auth';
import {useSalesData,DataState} from '@/lib/use-sales-data';
import {salesApi, type AIReviewItem} from '@/lib/sitepilot-api';

export const Route=createFileRoute('/sales/reviews')({component:DailyAIReview});

function FlagCard({flag, onReviewed}:{flag:AIReviewItem,onReviewed:()=>void}){
  const {token}=useSalesAuth();
  const [note,setNote]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  async function submit(){
    if(note.trim().length<3)return;
    setBusy(true);setError('');
    try{await salesApi.resolveReview(token,flag.id,note);onReviewed();}
    catch(e){setError(e instanceof Error?e.message:'Could not record review');}
    finally{setBusy(false)}
  }
  return <article className="rounded-xl border p-4 space-y-3">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="font-semibold">{flag.buyer_name} · {flag.reason.replaceAll('_',' ')}</p>
      <p className="text-xs text-muted-foreground">{new Date(flag.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST · Project {flag.project_id}</p></div>
      <Link className="text-sm underline text-primary" to="/sales/leads/$id" params={{id:flag.lead_id}}>Review full conversation</Link>
    </div>
    <blockquote className="border-l-2 border-primary pl-3 text-sm break-words">{flag.source_message}</blockquote>
    {!flag.contact_consent && <p className="text-sm text-muted-foreground">Buyer has not opted in to follow-up communications. Do not initiate outreach without permission.</p>}
    <label className="block text-sm font-medium" htmlFor={'review-'+flag.id}>Sales-head review note</label>
    <textarea id={'review-'+flag.id} className="w-full rounded-lg border border-input bg-card p-3 text-sm" rows={2}
      placeholder="What did you verify, correct, or assign?" value={note} onChange={e=>setNote(e.target.value)}/>
    <button className="btn btn-primary" type="button" disabled={busy||note.trim().length<3} onClick={submit}>{busy?'Saving…':'Mark reviewed'}</button>
    {error&&<p className="text-sm text-destructive" role="alert">{error}</p>}
  </article>
}
function DailyAIReview(){
  const {user}=useSalesAuth();
  const queue=useSalesData(salesApi.aiReviews);
  if(user.role!=='sales_head')return <div role="alert" className="card-surface p-8">Only the authorized sales head can review flagged AI conversations.</div>;
  if(!queue.data)return <DataState loading={queue.loading} error={queue.error} retry={queue.reload}/>;
  const items=queue.data.items;
  return <div><PageTitle id="S6" title="Daily AI review"><button className="btn btn-ghost" onClick={queue.reload}>Refresh queue</button></PageTitle>
    <p className="mb-5 text-sm text-muted-foreground">Review these flagged chats every day. No automated review or guaranteed callback is implied. Check the approved fact sheet before responding. Displayed timestamps are in IST.</p>
    <Panel title={`Open AI review flags (${items.length})`}>
      {items.length?<div className="space-y-4">{items.map(flag=><FlagCard key={flag.id} flag={flag} onReviewed={queue.reload}/>)}</div>:
       <p className="text-sm text-muted-foreground">No open flags. Check again tomorrow or after new enquiries.</p>}
    </Panel></div>;
}
