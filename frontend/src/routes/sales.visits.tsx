import {createFileRoute, Link} from '@tanstack/react-router';
import {useState} from 'react';
import {PageTitle} from '@/components/ops';
import {salesApi} from '@/lib/sitepilot-api';
import {useSalesAuth} from '@/lib/sales-auth';
import {useSalesData,DataState} from '@/lib/use-sales-data';

export const Route=createFileRoute('/sales/visits')({component:Visits});

function Visits(){
  const {token}=useSalesAuth();
  const {data,error,loading,reload}=useSalesData(salesApi.bookings);
  const [selected,setSelected]=useState('');
  const [saving,setSaving]=useState(false);
  const [actionError,setActionError]=useState('');
  if(!data)return <DataState loading={loading} error={error} retry={reload}/>;
  const current=data.find(x=>x.booking_id===selected);
  const confirmed=data.filter(b=>b.status==='confirmed').length;
  const completed=data.filter(b=>b.status==='attended').length;
  const noShows=data.filter(b=>b.status==='no_show').length;
  const cancelled=data.filter(b=>b.status==='cancelled').length;
  async function outcome(status:'attended'|'no_show'){
    if(!current||current.status!=='confirmed')return;
    setSaving(true);setActionError('');
    try{await salesApi.attendance(token,current.booking_id,status);reload()}
    catch(e){setActionError(e instanceof Error?e.message:'Update failed')}
    finally{setSaving(false)}
  }
  return <div>
    <PageTitle id="S4" title="Site visits"/>
    <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
      {([['Confirmed',confirmed],['Completed',completed],['No-shows',noShows],['Cancelled',cancelled]] as const).map(([label,count])=><div key={label} className="card-surface p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-display text-3xl font-semibold">{count}</p></div>)}
    </div>
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      <div className="card-surface overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm"><thead><tr>{['Reference','Date','Buyer','Project','Status'].map(h=><th key={h} className="p-3 text-left">{h}</th>)}</tr></thead>
          <tbody>{data.map(b=><tr key={b.booking_id} className="border-t border-border hover:bg-secondary"><td className="p-3"><button className="text-primary underline" onClick={()=>{setSelected(b.booking_id);setActionError('')}}>{b.booking_id.slice(0,8)}</button></td><td className="p-3">{new Date(b.starts_at).toLocaleString('en-IN')}</td><td className="p-3">{b.lead_name}</td><td className="p-3">{b.project_id}</td><td className="p-3">{b.status==='attended'?'Completed':b.status==='no_show'?'No-show':b.status}</td></tr>)}</tbody>
        </table>
        {data.length===0&&<p className="p-8 text-center text-muted-foreground">No visits booked yet.</p>}
      </div>
      <aside className="card-surface h-fit p-5">
        {current?<><p className="font-semibold">{current.lead_name}</p><p className="mt-1 text-sm">{new Date(current.starts_at).toLocaleString('en-IN')}</p><p className="mt-2 text-sm">Status: {current.status==='attended'?'Completed':current.status}</p><Link className="mt-3 block text-sm text-primary" to="/sales/leads/$id" params={{id:current.lead_id}}>Open lead →</Link><p className="mt-5 font-semibold">Record visit outcome</p><div className="mt-2 flex flex-wrap gap-2"><button className="btn btn-primary" disabled={saving||current.status!=='confirmed'} onClick={()=>outcome('attended')}>Mark completed</button><button className="btn btn-ghost" disabled={saving||current.status!=='confirmed'} onClick={()=>outcome('no_show')}>Mark no-show</button></div><p className="mt-2 text-xs text-muted-foreground">Attendance can only be recorded for a started, confirmed visit. Completed count uses recorded attendance, not elapsed time.</p>{actionError&&<p role="alert" className="mt-2 text-sm text-destructive">{actionError}</p>}</>:<p className="text-sm text-muted-foreground">Select a visit to inspect and record attendance.</p>}
      </aside>
    </div>
  </div>;
}
