import { createFileRoute, Link } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { Logo } from '@/components/site';
import { BuyerTicketPanel } from '@/components/ticket-panel';
import { backendProjectId, buyerSession, sitepilotApi, chatApi, type PublicSalesperson, type ApiProject, ApiError } from '@/lib/sitepilot-api';

type Search = {project?:string};
export const Route = createFileRoute('/chat')({
  validateSearch:(s:Record<string,unknown>):Search=>({project:typeof s.project==='string'?s.project:undefined}),
  component: Chat,
});
type Offer={slot_id:string;project_id:string;starts_at:string;ends_at:string;timezone:string};
type Bubble={id:number; speaker:'buyer'|'ai'|'sales'|'system'; text:string; concern?:{category:string;evidence:string;certainty:string}; offers?:Offer[]; strategy?:string};
const languageOptions=[{value:'en',label:'English'},{value:'hi',label:'हिन्दी'},{value:'gu',label:'ગુજરાતી'}] as const;
function Chat(){
  const {project} = Route.useSearch();
  const [published,setPublished] = useState<ApiProject[]>([]);
  const [catalogState,setCatalogState] = useState<'loading'|'ready'|'error'>('loading');
  useEffect(()=>{
    let active=true;
    sitepilotApi.projects().then(items=>{
      if(active){setPublished(items);setCatalogState('ready');}
    }).catch(()=>{if(active)setCatalogState('error');});
    return ()=>{active=false};
  },[]);
  const requestedId=project?backendProjectId(project):null;
  const current=published.find(item=>item.id===requestedId);
  if(catalogState==='loading') return <div className="min-h-dvh bg-background p-8 text-center" role="status">Loading published projects…</div>;
  if(catalogState==='error') return <div className="min-h-dvh bg-background p-8 text-center"><p role="alert">Unable to load the current projects. Check FastAPI and refresh the page.</p><Link to="/" className="mt-4 inline-block underline">Return to homepage</Link></div>;
  if(!current) return <ProjectPicker projects={published} previousProjectUnavailable={Boolean(requestedId)}/>;
  // Remount all state when switching projects. Tokens and chat history are
  // scoped to each project, so archived lead sessions cannot leak into a new one.
  return <ProjectChat key={current.id} backendId={current.id} projectLabel={current.name}/>;
}

function ProjectPicker({projects,previousProjectUnavailable}:{projects:ApiProject[];previousProjectUnavailable:boolean}){
  return <div className="min-h-dvh bg-background">
    <header className="border-b border-border bg-card"><div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-5"><Logo/><Link to="/" className="text-sm underline">All projects</Link></div></header>
    <main className="mx-auto max-w-3xl px-5 py-12">
      <p className="eyebrow">SitePilot AI</p>
      <h1 className="mt-3 text-4xl">Choose a project to discuss</h1>
      {previousProjectUnavailable?<p role="alert" className="mt-5 rounded-2xl border border-destructive/30 bg-card p-4 text-sm">This chat link belongs to a project that is no longer published. Your old conversation has not been deleted. Please select a current project to start a separate enquiry.</p>:<p className="mt-4 text-muted-foreground">Select one of the currently published projects. Each project has its own enquiry, conversation, and visit availability.</p>}
      {projects.length===0?<p className="mt-8 rounded-xl border p-5" role="status">No projects are currently published. You can return to the homepage or contact the sales team.</p>:<div className="mt-8 grid gap-4 sm:grid-cols-2">{projects.map(item=><Link key={item.id} to="/chat" search={{project:item.id}} className="rounded-2xl border bg-card p-5 transition hover:border-primary"><h2 className="font-semibold">{item.name}</h2><p className="mt-1 text-sm text-muted-foreground">{item.city}</p><p className="mt-3 text-sm">Start a conversation →</p></Link>)}</div>}
    </main>
  </div>;
}

function ProjectChat({backendId,projectLabel}:{backendId:string;projectLabel:string}){
  const [token,setToken]=useState<string|null>(null);
  const [ticketState,setTicketState]=useState('ai_active');
  const [identity,setIdentity]=useState({name:'',phone:'',contact_consent:false});
  const [language,setLanguage]=useState<'en'|'hi'|'gu'>('en');
  const [messages,setMessages]=useState<Bubble[]>([]);
  const [input,setInput]=useState('');
  const [busy,setBusy]=useState(false);
  const [backendBuild,setBackendBuild]=useState('checking');
  const [historyLoaded,setHistoryLoaded]=useState(false);
  const [error,setError]=useState('');
  const [handoffRequested,setHandoffRequested]=useState(false);
  const [handoffStatus,setHandoffStatus]=useState('');
  const [projectContacts,setProjectContacts]=useState<PublicSalesperson[]>([]);
  const [allowCallback,setAllowCallback]=useState(false);
  const [selectedOffer,setSelectedOffer]=useState<Offer|null>(null);
  const [confirmBusy,setConfirmBusy]=useState(false);
  const [bookingRef,setBookingRef]=useState<string|null>(null);
  const [bookingError,setBookingError]=useState('');
  const idCounter=useRef(0);
  const offlineNoticeShown=useRef(false);
  const end=useRef<HTMLDivElement>(null);
  const add=(speaker:Bubble['speaker'],text:string,concern?:Bubble['concern'],offers?:Offer[],strategy?:string)=>setMessages(prev=>[...prev,{id:++idCounter.current,speaker,text,concern,offers,strategy}]);
  useEffect(()=>{setToken(buyerSession.load(backendId));},[backendId]);
  useEffect(()=>{if(!token)return;chatApi.handoffStatus(token).then(s=>{if(s.status==='handoff_requested'){setHandoffRequested(true);setHandoffStatus(s.message);setProjectContacts(s.salespeople??[])}}).catch(()=>{});},[token]);
  useEffect(()=>{
    sitepilotApi.health().then(x=>setBackendBuild(x.build??'older backend')).catch(()=>setBackendBuild('unreachable'));
  },[]);
  useEffect(()=>{end.current?.scrollIntoView({behavior:'smooth'});},[messages,busy]);
  useEffect(()=>{
    if(!token)return;
    chatApi.history(token).then(items=>{
      setMessages(items.map((m,i)=>({id:i+1,speaker:m.speaker,text:m.message})));
      idCounter.current=items.length;
      setHistoryLoaded(items.length>0);
    }).catch(()=>{/* New or expired session: no history loaded. */});
  },[token]);
  useEffect(()=>{
    if(!token||!['accepted','resolved'].includes(ticketState))return;
    const refresh=()=>chatApi.history(token).then(items=>{
      setMessages(items.map((m,i)=>({id:i+1,speaker:m.speaker,text:m.message})));
      idCounter.current=items.length;
    }).catch(()=>{});
    void refresh();const id=setInterval(refresh,5000);return()=>clearInterval(id);
  },[token,ticketState]);
  const createSession=async(e:React.FormEvent)=>{
    e.preventDefault();setError('');setBusy(true);
    try{
      const r=await sitepilotApi.createLead({name:identity.name,phone:identity.phone,project_id:backendId,source:'website',contact_consent:identity.contact_consent});
      buyerSession.save(backendId,r.buyer_session_token);setToken(r.buyer_session_token);
    }catch(err){setError(err instanceof Error?err.message:'Unable to begin conversation');}finally{setBusy(false);}
  };
  const send=async(text:string)=>{
    if(!text.trim()||!token||busy)return;
    const clean=text.trim();setInput('');add('buyer',clean);setBusy(true);setError('');
    try{
      const r=await chatApi.send(token,clean,language);
      if(r.build) setBackendBuild(r.build);
      // Match the selector to a language requested in the conversation, including Romanized Hindi.
      if(r.response_language && r.response_language!==language) setLanguage(r.response_language);
      if(r.ai_status==='local_classifier' && !offlineNoticeShown.current){
        add('system','The local language model is offline. Limited, locally trained intent assistance is active; property facts and booking rules remain verified by the server.');
        offlineNoticeShown.current=true;
      }
      if(r.reply)add('ai',r.reply,r.hesitation??undefined,r.booking_options,r.reply_strategy);
      else add('system',r.message??'AI is unavailable. You can request human assistance.');
    }catch(err){
      const archived = err instanceof ApiError && err.status===404 && /project/i.test(err.detail);
      add('system',archived?'This project is no longer available for new enquiries. Select a current project above.':'The message could not be processed. Please try again or request a person.');
      setError(archived?'Please choose a published project using Change project.':err instanceof Error?err.message:'Unable to send');
    }
    finally{setBusy(false);}
  };
  const confirmVisit=async()=>{
    if(!token||!selectedOffer||confirmBusy)return;
    setConfirmBusy(true);setBookingError('');
    try {
      // One key per explicit confirmation attempt. Retry reuses the same key if network fails.
      const key=confirmationKey.current ?? crypto.randomUUID();
      confirmationKey.current=key;
      const booking=await sitepilotApi.book(selectedOffer.project_id,selectedOffer.slot_id,token,key);
      setBookingRef(booking.booking_id);setSelectedOffer(null);confirmationKey.current=null;
      add('system',`Your site visit is confirmed. Reference: ${booking.booking_id}.`);
    } catch (err) {
      setBookingError(err instanceof Error?err.message:'Could not confirm booking. Please check availability.');
      // Keep key on transport errors for idempotent retry; reset after definite conflict.
      if(err instanceof Error && /unavailable|conflict|409/i.test(err.message))confirmationKey.current=null;
    } finally {setConfirmBusy(false);}
  };
  const confirmationKey=useRef<string|null>(null);
  const handoff=async()=>{
    if(busy||handoffRequested)return;
    if(!token){
      setError('');
      try{const contacts=await sitepilotApi.publicSalespeople(backendId);setProjectContacts(contacts);setHandoffStatus('These are the available project sales contacts. Start an enquiry below to request a follow-up.');}
      catch(err){setError(err instanceof Error?err.message:'Unable to load salesperson contacts');}
      return;
    }
    setBusy(true);setError('');
    try{if(allowCallback)await chatApi.consent(token,true);const r=await chatApi.handoff(token);setHandoffRequested(true);setHandoffStatus(r.message);setProjectContacts(r.salespeople??[]);}
    catch(err){setError(err instanceof Error?err.message:'Unable to request handoff');}
    finally{setBusy(false);}
  };
  return <div className="flex h-dvh flex-col bg-background">
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-4"><Logo/><div className="border-l border-border pl-4"><p className="text-sm font-semibold">SitePilot AI · {projectLabel}</p><p className="text-xs text-muted-foreground">AI-assisted enquiry · Verified facts only</p></div></div>
        <div className="flex items-center gap-2">
          <Link to="/chat" search={{}} className="text-xs underline underline-offset-2">Start another enquiry</Link>
          <label className="sr-only" htmlFor="language">Language</label>
          <select id="language" className="h-11 rounded-full border bg-background px-3 text-sm" value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{languageOptions.map(l=><option key={l.value} value={l.value}>{l.label}</option>)}</select>
          <button className="btn btn-ghost" onClick={handoff} disabled={busy||handoffRequested||['accepted','resolved'].includes(ticketState)}>{['accepted','resolved'].includes(ticketState)?'Assigned':handoffRequested?'Request sent':'Talk to salesperson'}</button>
          <Link to="/book" search={{project:backendId}} className="btn btn-primary hidden sm:inline-flex">Book visit</Link>
        </div>
      </div>
    </header>
    {backendBuild==='unreachable'&&<div className="border-b px-4 py-2 text-center text-xs text-destructive" role="status">The chat API is unavailable. Please check the FastAPI connection and try again.</div>}
    <main className="flex-1 overflow-y-auto"><div className="mx-auto max-w-3xl space-y-5 px-4 py-8">
      {handoffStatus&&<section role="status" className="rounded-xl border border-primary/30 bg-card p-4 text-sm"><strong>Salesperson request</strong><p className="mt-1">{handoffStatus}</p>{projectContacts.length?<div className="mt-3 grid gap-3 sm:grid-cols-2">{projectContacts.map(c=><div key={c.id} className="rounded-xl border bg-background p-3"><p className="font-semibold">{c.name}</p><p className="text-xs text-muted-foreground">{c.role_title} · Project contact</p><p className="mt-2"><a href={`tel:${c.phone}`} className="underline">Call {c.phone}</a></p><p><a href={`mailto:${c.email}`} className="underline">Email {c.email}</a></p></div>)}</div>:<p className="mt-2 text-xs text-muted-foreground">No approved project contact has been published yet. Your enquiry is in the sales team's queue.</p>}</section>}
      {token&&!handoffRequested&&<label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={allowCallback} onChange={e=>setAllowCallback(e.target.checked)}/> Allow a salesperson to contact me about this enquiry when I request a handoff.</label>}
      {token&&<BuyerTicketPanel token={token} onStatusChange={setTicketState}/>}
      {token && historyLoaded && <p className="text-center text-xs text-muted-foreground">Your previous messages have been restored.</p>}
      {!token?<div className="mx-auto max-w-md rounded-3xl border bg-card p-7 shadow-sm">
        <h1 className="mb-2 text-2xl font-semibold">Start a private conversation</h1><p className="mb-5 text-sm text-muted-foreground">Please introduce yourself to save your enquiry. Messages are AI-assisted; ask for a person at any time.</p>
        <form onSubmit={createSession} className="space-y-4">
          <label className="block text-sm">Your name<input className="mt-1 h-11 w-full rounded-xl border bg-background px-4" minLength={2} required value={identity.name} onChange={e=>setIdentity(x=>({...x,name:e.target.value}))}/></label>
          <label className="block text-sm">Phone number<input className="mt-1 h-11 w-full rounded-xl border bg-background px-4" pattern="[+]?[0-9]{10,15}" required placeholder="10 digit mobile number" value={identity.phone} onChange={e=>setIdentity(x=>({...x,phone:e.target.value}))}/></label>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={identity.contact_consent} onChange={e=>setIdentity(x=>({...x,contact_consent:e.target.checked}))}/><span>I agree to receive follow-up communications. Optional; you can opt out later.</span></label>
          {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
          <button className="btn btn-primary w-full" disabled={busy}>{busy?'Starting…':'Start conversation'}</button>
        </form>
      </div>:<>
        {messages.length===0&&<div className="rounded-3xl border bg-card p-6"><p className="font-semibold">Hello, I'm SitePilot, an AI assistant.</p><p className="mt-2 text-sm text-muted-foreground">Ask about approved project facts, visit availability or speak to a person. Some project details are not yet verified.</p></div>}
        {messages.map(m=><div key={m.id} className={m.speaker==='buyer'?'ml-auto max-w-[85%] rounded-3xl rounded-br-md bg-primary px-5 py-3 text-primary-foreground':'max-w-[85%] rounded-3xl rounded-bl-md border bg-card px-5 py-3'}>
          <p className="whitespace-pre-wrap">{m.text}</p>{m.offers?.length ? <div className="mt-3 flex flex-col gap-2">{m.offers.map(o=><button key={o.slot_id} type="button" onClick={()=>{setSelectedOffer(o);setBookingError('');confirmationKey.current=null;}} className="rounded-xl border px-3 py-2 text-left text-sm hover:bg-muted">{new Date(o.starts_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})} · Choose this time</button>)}</div>:null}
        </div>)}
        {selectedOffer&&<section className="rounded-2xl border bg-card p-5" aria-label="Confirm site visit"><h2 className="font-semibold">Confirm this site visit?</h2><p className="my-2 text-sm">{projectLabel} · {new Date(selectedOffer.starts_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'full',timeStyle:'short'})}</p><p className="mb-3 text-xs text-muted-foreground">The time is not reserved until the backend confirms it.</p><div className="flex gap-2"><button type="button" className="btn btn-primary" disabled={confirmBusy} onClick={confirmVisit}>{confirmBusy?'Confirming…':'Confirm booking'}</button><button type="button" className="btn btn-ghost" onClick={()=>setSelectedOffer(null)} disabled={confirmBusy}>Not now</button></div>{bookingError&&<p role="alert" className="mt-2 text-sm text-red-700">{bookingError} Select a new time if it is occupied.</p>}</section>}
        {bookingRef&&<p role="status" className="rounded-xl border p-3 text-sm">Booking confirmed · Reference: {bookingRef}. <Link to="/buyer/visits" className="underline">Manage or secure your visit</Link></p>}
        {busy&&<p role="status" className="text-sm text-muted-foreground">Checking your request… For longer questions the local AI may need a few seconds.</p>}
        {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
        <div ref={end}/>
      </>}
    </div></main>
    {token&&<footer className="border-t bg-card"><div className="mx-auto max-w-3xl px-4 py-3">
      <div className="mb-3 flex flex-wrap gap-2">{['What project information is approved?','Show me visit times.','Talk to a salesperson.'].map(s=><button key={s} className="chip" disabled={busy} onClick={()=>send(s)}>{s}</button>)}</div>
      <form onSubmit={e=>{e.preventDefault();void send(input);}} className="flex gap-2"><label htmlFor="chatmsg" className="sr-only">Message</label><input id="chatmsg" className="h-12 flex-1 rounded-full border bg-background px-5 text-sm" value={input} maxLength={3000} onChange={e=>setInput(e.target.value)} placeholder="Ask a question…"/><button className="btn btn-primary" disabled={busy||!input.trim()}>Send</button></form>
    </div></footer>}
  </div>;
}
