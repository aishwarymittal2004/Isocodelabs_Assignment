import {createFileRoute,Link,Outlet} from '@tanstack/react-router';
import {useEffect,useState,type FormEvent} from 'react';
import {salesApi} from '@/lib/sitepilot-api';
import {SalesAuthContext,type SalesIdentity} from '@/lib/sales-auth';
export const Route=createFileRoute('/sales')({component:SalesLayout});
const nav=[{to:'/sales',label:'Dashboard'},{to:'/sales/leads',label:'Leads'},{to:'/sales/tickets',label:'Ticket ownership'},{to:'/sales/visits',label:'Visits'},{to:'/sales/analytics',label:'Analytics'},{to:'/sales/reviews',label:'AI review'},{to:'/sales/admin',label:'Projects, facts & slots'}] as const;
function SalesLayout(){
 const [token,setToken]=useState('');const [user,setUser]=useState<SalesIdentity|null>(null);const [open,setOpen]=useState(false);const [checking,setChecking]=useState(true);
 useEffect(()=>{const stored=sessionStorage.getItem('sitepilot_sales_token');if(!stored){setChecking(false);return;}salesApi.me(stored).then(u=>{setToken(stored);setUser(u)}).catch(()=>sessionStorage.removeItem('sitepilot_sales_token')).finally(()=>setChecking(false));},[]);
 function logout(){sessionStorage.removeItem('sitepilot_sales_token');setToken('');setUser(null)}
 if(checking)return <div className="min-h-screen grid place-items-center" role="status">Checking sales session…</div>;
 if(!user)return <SalesLogin onLogin={(t,u)=>{sessionStorage.setItem('sitepilot_sales_token',t);setToken(t);setUser(u)}}/>;
 return <SalesAuthContext.Provider value={{token,user,logout}}><div className="min-h-screen bg-secondary md:flex">
 <aside className={`${open?'block':'hidden'} fixed inset-y-0 left-0 z-30 w-60 bg-sidebar p-4 text-sidebar-foreground md:sticky md:top-0 md:block md:h-screen`}>
 <Link to="/" className="flex items-center gap-2 px-2 py-3 font-display text-xl">SitePilot</Link><p className="px-2 text-xs text-sidebar-foreground/60">Sales workspace</p>
 <nav className="mt-6 space-y-1">{nav.filter(n=>n.to!='/sales/reviews'||user.role==='sales_head').map(n=><Link key={n.to} to={n.to} onClick={()=>setOpen(false)} className="block rounded-lg px-3 py-2.5 text-sm hover:bg-sidebar-accent" activeProps={{className:'!bg-sidebar-accent font-semibold'}}>{n.label}</Link>)}</nav>
 <div className="absolute inset-x-4 bottom-4 rounded-lg bg-sidebar-accent p-3 text-xs"><p className="font-semibold">{user.display_name}</p><p className="text-sidebar-foreground/60">Signed in · sales workspace</p><button className="mt-3 underline" onClick={logout}>Sign out</button></div></aside>
 <div className="min-w-0 flex-1"><header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:px-6"><button className="btn btn-ghost !min-h-9 md:hidden" onClick={()=>setOpen(!open)} aria-label="Toggle menu">☰</button><p className="text-xs text-muted-foreground">Live backend records · sample data may be present</p><Link to="/" className="text-sm font-medium text-primary">Buyer site →</Link></header><main className="p-4 md:p-6"><Outlet/></main></div></div></SalesAuthContext.Provider>
}
function SalesLogin({onLogin}:{onLogin:(token:string,user:SalesIdentity)=>void}){
 const [mode,setMode]=useState<'login'|'invite'>('login');
 const [email,setEmail]=useState('');
 const [password,setPassword]=useState('');
 const [invitationCode,setInvitationCode]=useState('');
 const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
 async function submit(event:FormEvent){
  event.preventDefault();setBusy(true);setError('');setNotice('');
  try{
   if(mode==='invite'){
    await salesApi.acceptInvitation(email,invitationCode,password);
    setMode('login');setPassword('');setInvitationCode('');
    setNotice('Account created successfully. Sign in with your new password.');
   }else{
    const auth=await salesApi.login(email,password);
    const user=await salesApi.me(auth.access_token);
    onLogin(auth.access_token,user);
   }
  }catch(e){setError(e instanceof Error?e.message:'Unable to complete your request')}finally{setBusy(false)}
 }
 return <div className="min-h-screen grid place-items-center bg-secondary px-4"><div className="card-surface w-full max-w-md p-8">
  <Link to="/" className="font-display text-2xl">SitePilot</Link>
  <h1 className="mt-6 text-2xl">{mode==='login'?'Sales sign in':'Activate your sales account'}</h1>
  <p className="mt-2 text-sm text-muted-foreground">{mode==='login'?'Sign in with the account assigned to you by your sales head.':'New sales executives use a one-time code issued by the sales head; public signup is disabled.'}</p>
  <form onSubmit={submit} className="mt-5 space-y-3">
   <label className="block text-sm">Email<input type="email" required autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 h-11 w-full rounded-lg border border-input px-3"/></label>
   {mode==='invite'&&<label className="block text-sm">Invitation code<input required minLength={30} autoComplete="off" value={invitationCode} onChange={e=>setInvitationCode(e.target.value.trim())} className="mt-2 h-11 w-full rounded-lg border border-input px-3"/></label>}
   <label className="block text-sm">{mode==='invite'?'Choose a password (12+ characters)':'Password'}<input type="password" required minLength={mode==='invite'?12:undefined} maxLength={128} autoComplete={mode==='invite'?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 h-11 w-full rounded-lg border border-input px-3"/></label>
   {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}
   {notice&&<p role="status" className="text-sm text-primary">{notice}</p>}
   <button disabled={busy} className="btn btn-primary mt-3 w-full" type="submit">{busy?'Please wait…':mode==='login'?'Sign in':'Create sales account'}</button>
  </form>
  <button type="button" className="mt-4 text-sm underline" onClick={()=>{setMode(mode==='login'?'invite':'login');setError('');setNotice('');setPassword('')}}>{mode==='login'?'New sales executive? Activate an invitation':'Already registered? Sign in'}</button>
 </div></div>;
}
