import { createFileRoute, Link } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { SiteHeader } from '@/components/site';
import { ApiError, buyerSession, sitepilotApi, type ApiBooking, type ApiProject } from '@/lib/sitepilot-api';

export const Route = createFileRoute('/buyer/visits')({component: MyVisits});
function formatWhen(iso:string){return new Date(iso).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'});}
function MyVisits(){
 const [projects,setProjects]=useState<ApiProject[]>([]);
 const [project,setProject]=useState('project-1');
 const [phone,setPhone]=useState('');
 const [accountMode,setAccountMode]=useState<'login'|'register'>('login');
 const [name,setName]=useState('');
 const [consent,setConsent]=useState(false);
 const [password,setPassword]=useState('');
 const [token,setToken]=useState('');
 const [bookings,setBookings]=useState<ApiBooking[]>([]);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [cancelId,setCancelId]=useState<string|null>(null);
 const [claimPassword,setClaimPassword]=useState('');
 const [hasAccount,setHasAccount]=useState<boolean|null>(null);
 useEffect(()=>{sitepilotApi.projects().then(rows=>{setProjects(rows);if(rows.length&&!rows.some(p=>p.id===project))setProject(rows[0].id)}).catch(()=>setError('Unable to load projects'));},[]);
 useEffect(()=>{setToken(buyerSession.load(project)??'');setBookings([]);setError('');},[project]);
 useEffect(()=>{if(!token){setHasAccount(null);return;}sitepilotApi.buyerMe(token).then(x=>setHasAccount(x.has_account)).catch(()=>setHasAccount(null));sitepilotApi.bookings(token).then(setBookings).catch(()=>{setToken('');setError('This session expired. Sign in again to manage your appointments.');});},[token]);
 const submitAccount=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setError('');setNotice('');try{
   const result=accountMode==='login'
     ? await sitepilotApi.loginBuyer(phone.trim(),password,project)
     : await sitepilotApi.registerBuyer({name:name.trim(),phone:phone.trim(),password,project_id:project,contact_consent:consent});
   buyerSession.save(project,result.buyer_session_token);setToken(result.buyer_session_token);setPassword('');
   setHasAccount(true);setNotice(accountMode==='login'?'Signed in. Your visits are shown below.':'Account created. You can now book a visit. Older visits are not automatically imported.');
 }catch(err){
   if(accountMode==='register' && err instanceof ApiError && err.status===409 && /account exists/i.test(err.detail)){
     setAccountMode('login');setPassword('');
     setNotice('This phone is already registered for the selected project. Sign in with its existing password. Your bookings are preserved.');
   }else if(accountMode==='login' && err instanceof ApiError && err.status===401){
     setError('Sign-in failed. Check the selected project, phone and original password. If you forgot it, request an identity-verified reset; do not create a duplicate account.');
   }else setError(err instanceof Error?err.message:'Could not access your account')
 }finally{setBusy(false)}};
 const cancel=async(id:string)=>{if(!token)return;setBusy(true);setError('');try{await sitepilotApi.cancel(id,token);setBookings(await sitepilotApi.bookings(token));setNotice('Visit cancelled. No visit reminders will be sent for this appointment.');setCancelId(null);}catch(err){setError(err instanceof Error?err.message:'Unable to cancel visit')}finally{setBusy(false)}};
 const secure=async(e:React.FormEvent)=>{e.preventDefault();if(!token)return;setBusy(true);setError('');try{await sitepilotApi.claimBuyer(token,claimPassword);setClaimPassword('');setHasAccount(true);setNotice('Your existing browser booking is secured. You can now sign in after this session expires.')}catch(err){setError(err instanceof Error?err.message:'Could not protect this session')}finally{setBusy(false)}};
 return <div className="min-h-screen bg-background"><SiteHeader/><main className="mx-auto max-w-4xl px-5 py-12"><p className="eyebrow">Buyer account</p><h1 className="mt-2 text-4xl">My site visits</h1><p className="mt-3 max-w-2xl text-muted-foreground">Sign in using the phone number, project and password you chose when booking. You can cancel a confirmed visit without contacting the sales team.</p>
 <label className="mt-8 block max-w-md text-sm font-semibold">Project<select value={project} onChange={e=>setProject(e.target.value)} className="mt-2 w-full rounded-xl border bg-card p-3">{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
 {error&&<p role="alert" className="mt-4 rounded-xl border border-destructive/30 p-3 text-sm text-destructive">{error}</p>}{notice&&<p role="status" className="mt-4 rounded-xl border border-primary/30 p-3 text-sm">{notice}</p>}
 {!token?<div className="mt-7 max-w-md space-y-4 rounded-2xl border bg-card p-6">
 <div className="flex gap-2" role="group" aria-label="Buyer account action">
  <button type="button" onClick={()=>{setAccountMode('login');setError('')}} className={accountMode==='login'?'btn btn-primary':'btn btn-ghost'}>Sign in</button>
  <button type="button" onClick={()=>{setAccountMode('register');setError('')}} className={accountMode==='register'?'btn btn-primary':'btn btn-ghost'}>Create account</button>
 </div>
 <h2 className="text-xl">{accountMode==='login'?'Sign in to manage bookings':'Create a buyer account'}</h2>
 <form onSubmit={submitAccount} className="space-y-4">
  {accountMode==='register'&&<label className="block text-sm">Full name<input required minLength={2} maxLength={120} autoComplete="name" value={name} onChange={e=>setName(e.target.value)} className="mt-1 w-full rounded-xl border p-3"/></label>}
  <label className="block text-sm">Phone number<input required pattern="[+]?[0-9]{10,15}" autoComplete="tel" value={phone} onChange={e=>setPhone(e.target.value)} className="mt-1 w-full rounded-xl border p-3"/></label>
  <label className="block text-sm">Password<input type="password" required minLength={accountMode==='register'?10:undefined} maxLength={128} autoComplete={accountMode==='login'?'current-password':'new-password'} value={password} onChange={e=>setPassword(e.target.value)} className="mt-1 w-full rounded-xl border p-3"/></label>
  {accountMode==='register'&&<label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} /><span>Optional: I agree to appointment reminders and follow-up contact.</span></label>}
  <button disabled={busy} className="btn btn-primary w-full">{busy?'Please wait…':accountMode==='login'?'Sign in':'Create account'}</button>
 </form>
 <p className="text-xs text-muted-foreground">Accounts are associated with the selected project. A temporary JWT issued for an older chat or booking is not automatically a password-protected account.</p>
 {accountMode==='register'?<p className="text-xs text-muted-foreground">Creating a new account does not recover previous bookings. If you still have your old booking session, use it to secure that account instead.</p>:<p className="text-xs text-muted-foreground">No password account yet? Select Create account or <Link to="/book" search={{project:undefined}} className="underline">book a visit</Link>. Forgot your original password? Contact an authorized staff member for verified assistance. For a local demo, the developer can reset it using the backend's development-only command. Phone number alone cannot recover an account.</p>}
 </div>:<div className="mt-8 space-y-5"><div className="flex items-center justify-between"><p className="font-semibold">Your appointments ({bookings.length})</p><button onClick={()=>{setToken('');setBookings([]);sessionStorage.removeItem(`sitepilot_buyer_${project}`)}} className="btn btn-ghost">Sign out</button></div>
 {!bookings.length?<div className="rounded-2xl border bg-card p-6">No bookings found for this project. <Link to="/book" search={{project:undefined}} className="underline">Find a visit time</Link></div>:bookings.map(b=><section key={b.booking_id} className="rounded-2xl border bg-card p-5"><div className="flex flex-wrap justify-between gap-3"><div><p className="font-semibold">{projects.find(p=>p.id===b.project_id)?.name??'Site visit'}</p><p className="mt-1 text-sm">{formatWhen(b.starts_at)}</p><p className="mt-1 text-xs text-muted-foreground">Reference: {b.booking_id}</p></div><span className="text-sm font-semibold capitalize">{b.status.replaceAll('_',' ')}</span></div>{b.status==='confirmed'&&<div className="mt-4">{cancelId===b.booking_id?<div role="group" aria-label="Confirm visit cancellation"><p className="mb-2 text-sm">Cancel this appointment? This action frees the slot for others.</p><div className="flex gap-2"><button className="btn btn-primary" disabled={busy} onClick={()=>void cancel(b.booking_id)}>Yes, cancel visit</button><button className="btn btn-ghost" onClick={()=>setCancelId(null)}>Keep visit</button></div></div>:<button className="btn btn-ghost" onClick={()=>setCancelId(b.booking_id)}>Cancel visit</button>}</div>}</section>)}
 {hasAccount===false&&<form onSubmit={secure} className="rounded-2xl border bg-card p-5"><h2 className="text-lg">Booked before accounts were added?</h2><p className="mt-1 text-sm text-muted-foreground">If this browser still has an unregistered buyer session, you can secure it with a password. Existing accounts cannot be claimed again.</p><div className="mt-3 flex flex-wrap gap-3"><input type="password" minLength={10} maxLength={128} required placeholder="New password (10+ characters)" value={claimPassword} onChange={e=>setClaimPassword(e.target.value)} className="min-w-56 flex-1 rounded-xl border p-3"/><button className="btn btn-ghost" disabled={busy}>Secure session</button></div></form>}</div>}
 </main></div>;
}
