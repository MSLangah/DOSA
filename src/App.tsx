import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { Menu, Settings, Wrench, Shield, LogOut } from 'lucide-react';
import { motion } from 'framer-motion';
import Papa from 'papaparse';
import JSZip from 'jszip';
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import { api } from './lib/api';
import { useToast } from './context/ToastContext';
import { Logo } from './components/Logo';

type User = { id: string; role: 'admin' | 'user'; display_name?: string; displayName?: string; email: string };

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState('admin@masspagebuilder.com');
  const [password, setPassword] = useState('admin123');
  const { push } = useToast();
  const submit = async () => {
    try {
      const data = await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      sessionStorage.setItem('sessionId', data.sessionId);
      onLogin(data.user);
    } catch (e: any) { push('error', e.message); }
  };
  return <div className="min-h-screen grid md:grid-cols-2">
    <motion.div initial={{opacity:0}} animate={{opacity:1}} className="bg-slate-900 text-white p-10 flex flex-col justify-center">
      <h1 className="text-4xl font-bold">Generate SEO Optimized Pages in Bulk</h1><p className="mt-4 text-slate-300">Bulk SEO Optimized Pages Generator | Mass Page Builder</p>
    </motion.div>
    <div className="p-8 flex items-center"><motion.div initial={{x:30,opacity:0}} animate={{x:0,opacity:1}} className="card w-full max-w-md mx-auto space-y-3"><Logo/><input className="input" value={email} onChange={e=>setEmail(e.target.value)}/><input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)}/><button className="btn w-full" onClick={submit}>Login</button></motion.div></div>
  </div>;
}

function ToolPage() {
  const { push } = useToast();
  const [template, setTemplate] = useState(''); const [keywordsText, setKeywordsText] = useState(''); const [apiKey, setApiKey] = useState('');
  const [progress, setProgress] = useState(0); const [current, setCurrent] = useState(''); const [counts, setCounts] = useState({ ok: 0, fail: 0 });
  const [showHelp, setShowHelp] = useState(false);
  const parse = (f: File) => f.text().then((t)=>f.name.endsWith('.csv')?Papa.parse<string[]>(t).data.flat().join('\n'):t);
  const run = async () => {
    const keywords = keywordsText.split('\n').map(s=>s.trim()).filter(Boolean).slice(0,50);
    if (!template || !keywords.length || !apiKey) return push('info', 'Provide template, keywords, and API key');
    const data = await api('/api/tool/generate',{method:'POST',body:JSON.stringify({template,keywords,apiKey})});
    const zip = new JSZip(); let ok=0,fail=0;
    data.results.forEach((r:any,i:number)=>{ setCurrent(r.keyword); setProgress(Math.round(((i+1)/data.results.length)*100)); if(r.html){ok++;zip.file(`${r.keyword.replace(/\W+/g,'-')}.html`,r.html);} else fail++; });
    setCounts({ok,fail}); const blob=await zip.generateAsync({type:'blob'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='seo-pages.zip'; a.click();
    push('success',`Generated ${ok} pages`);
  };
  return <div className="space-y-4"><div className="card space-y-2"><h2 className="font-semibold">Bulk Generator</h2><input type="file" accept=".html" onChange={e=>e.target.files?.[0]?.text().then(setTemplate)} /><input type="file" accept=".csv,.txt" onChange={async e=>{const f=e.target.files?.[0]; if(f)setKeywordsText(await parse(f));}}/><textarea className="input h-32" value={keywordsText} onChange={e=>setKeywordsText(e.target.value)} placeholder="keyword per line"/><input className="input" type="password" placeholder="OpenAI API Key" value={apiKey} onChange={e=>setApiKey(e.target.value)}/><button className="btn" onClick={run}>Generate Zip</button><button className="text-indigo-500" onClick={()=>setShowHelp(true)}>How to get OpenAI API for free?</button></div><div className="card"><div className="h-2 bg-slate-200 rounded"><div className="h-2 bg-indigo-500 rounded" style={{width:`${progress}%`}}/></div><p>Progress {progress}% | Current: {current} | ✅ {counts.ok} ❌ {counts.fail}</p></div>
  {showHelp && <div className="fixed inset-0 bg-black/50 grid place-items-center" onClick={()=>setShowHelp(false)}><div className="card max-w-lg" onClick={e=>e.stopPropagation()}><h3 className="font-bold">OpenAI Free Credits Guide</h3><ol className="list-decimal ml-5 text-sm"><li>Create account at platform.openai.com</li><li>Go to API Keys and generate a secret key</li><li>Use available trial credits to run generations</li></ol></div></div>}</div>;
}

function AdminPage() {
  const [analytics, setAnalytics] = useState<any>(); const [users, setUsers] = useState<any[]>([]); const [sessions, setSessions] = useState<any[]>([]); const [search,setSearch]=useState('');
  const load = async()=>{ setAnalytics(await api('/api/admin/analytics')); setUsers((await api('/api/admin/users')).users); setSessions((await api('/api/admin/sessions')).sessions);}; useEffect(()=>{load();},[]);
  const filtered=users.filter(u=>u.email.includes(search)||u.displayName?.includes(search));
  return <div className="space-y-4"><div className="grid md:grid-cols-3 gap-3">{analytics && [['DAU',analytics.metrics.dau],['Pages',analytics.metrics.pages],['Avg Session',analytics.metrics.session]].map(([k,v])=><div key={String(k)} className="card">{k}: {v}</div>)}</div>
  {analytics && <div className="grid md:grid-cols-3 gap-3"> <div className="card h-48"><ResponsiveContainer><AreaChart data={analytics.daily}><XAxis dataKey="day"/><YAxis/><Area dataKey="users"/></AreaChart></ResponsiveContainer></div><div className="card h-48"><ResponsiveContainer><BarChart data={analytics.daily}><XAxis dataKey="day"/><YAxis/><Bar dataKey="pages"/></BarChart></ResponsiveContainer></div><div className="card h-48"><ResponsiveContainer><LineChart data={analytics.daily}><XAxis dataKey="day"/><YAxis/><Line dataKey="duration"/></LineChart></ResponsiveContainer></div></div>}
  <div className="card"><div className="flex justify-between"><h3>Users</h3><input className="input w-64" placeholder="search" value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="space-y-2 mt-2">{filtered.map(u=><div key={u.id} className="group p-2 border rounded flex justify-between"><div>{u.displayName} ({u.email}) - {u.role}</div><div className="opacity-0 group-hover:opacity-100 space-x-2"><button className="text-sm" onClick={async()=>{await api(`/api/admin/users/${u.id}`,{method:'PUT',body:JSON.stringify({displayName:u.displayName,role:u.role==='admin'?'user':'admin'})});load();}}>Edit</button><button className="text-sm text-rose-500" onClick={async()=>{await api(`/api/admin/users/${u.id}`,{method:'DELETE'});load();}}>Delete</button></div></div>)}</div></div>
  <div className="card space-y-2">{sessions.map(s=><div key={s.id} className="p-2 border rounded flex justify-between"><div>{s.displayName} | {s.userAgent} | {s.revokedAt?'Idle':'Active'}</div><button className="text-rose-500" onClick={async()=>{await api(`/api/admin/sessions/${s.id}/terminate`,{method:'POST'});load();}}>TERMINATE</button></div>)}</div></div>;
}

function SettingsPage() {
  const { push } = useToast();
  const [displayName,setDisplayName]=useState(''); const [currentPassword,setCurrent]=useState(''); const [newPassword,setNew]=useState(''); const [sessions,setSessions]=useState<any[]>([]);
  const strength = useMemo(()=> newPassword.length>10?'Strong':newPassword.length>6?'Medium':'Weak',[newPassword]);
  const load = async()=>setSessions((await api('/api/settings/sessions')).sessions); useEffect(()=>{load();},[]);
  return <div className="space-y-4"><div className="card space-y-2"><h3>Profile</h3><input className="input" placeholder="Display Name" value={displayName} onChange={e=>setDisplayName(e.target.value)}/><button className="btn" onClick={async()=>{await api('/api/settings/profile',{method:'PUT',body:JSON.stringify({displayName})});push('success','Profile updated');}}>Save</button></div>
  <div className="card space-y-2"><h3>Password</h3><input className="input" type="password" placeholder="Current" value={currentPassword} onChange={e=>setCurrent(e.target.value)}/><input className="input" type="password" placeholder="New" value={newPassword} onChange={e=>setNew(e.target.value)}/><p className={strength==='Strong'?'text-emerald-500':strength==='Medium'?'text-yellow-500':'text-rose-500'}>{strength}</p><button className="btn" onClick={async()=>{await api('/api/settings/password',{method:'PUT',body:JSON.stringify({currentPassword,newPassword})});push('success','Password changed');}}>Change</button></div>
  <div className="card">{sessions.map(s=><div key={s.id} className="p-2 border rounded flex justify-between mb-2"><div>{s.ip} | {s.user_agent} | {s.last_active_at}</div><button className="text-rose-500" onClick={async()=>{await api(`/api/settings/sessions/${s.id}/revoke`,{method:'POST'});load();}}>Revoke</button></div>)}</div></div>;
}

export function App() {
  const [user, setUser] = useState<User | null>(null); const [open,setOpen]=useState(false); const nav=useNavigate();
  useEffect(() => { api('/api/auth/me').then((d) => setUser(d.user)).catch(() => {}); }, []);
  useEffect(() => {
    if (!user) return;
    let t = Date.now(); const onA = ()=> t=Date.now(); ['mousemove','click','keydown','scroll'].forEach(e=>window.addEventListener(e,onA));
    const i=setInterval(async()=>{ if(Date.now()-t>20*60*1000){ await api('/api/auth/logout',{method:'POST'}).catch(()=>{}); sessionStorage.removeItem('sessionId'); setUser(null); }
      else await api('/api/auth/heartbeat',{method:'POST'}).catch(()=>{});
    },120000);
    return ()=>{clearInterval(i); ['mousemove','click','keydown','scroll'].forEach(e=>window.removeEventListener(e,onA));};
  }, [user]);
  useEffect(()=>{ const v=localStorage.getItem('theme')||'system'; const root=document.documentElement; root.classList.toggle('dark', v==='dark' || (v==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches));},[]);

  if (!user) return <Login onLogin={setUser} />;
  return <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]"><aside className={`md:block ${open?'block':'hidden'} bg-white dark:bg-slate-900 border-r p-4 space-y-3`}><Logo/><Link to="/" className="flex gap-2"><Wrench/>Tool</Link>{user.role==='admin'&&<Link to="/admin" className="flex gap-2"><Shield/>Admin Panel</Link>}<Link to="/settings" className="flex gap-2"><Settings/>Account Settings</Link><button className="flex gap-2" onClick={async()=>{await api('/api/auth/logout',{method:'POST'});sessionStorage.removeItem('sessionId');setUser(null);nav('/');}}><LogOut/>Logout</button><div><select className="input" onChange={e=>{localStorage.setItem('theme',e.target.value);location.reload();}} defaultValue={localStorage.getItem('theme')||'system'}><option value='light'>Light</option><option value='dark'>Dark</option><option value='system'>System</option></select></div></aside><main className="p-4"><button className="md:hidden mb-2" onClick={()=>setOpen(!open)}><Menu/></button><Routes><Route path="/" element={<ToolPage/>}/><Route path="/admin" element={user.role==='admin'?<AdminPage/>:<Navigate to='/'/>}/><Route path="/settings" element={<SettingsPage/>}/></Routes><footer className="mt-8 text-sm text-slate-500">© {new Date().getFullYear()} Mass Page Builder | Developed by <a href="https://shahbazshafat.com" className="underline">Shahbaz Shafat</a></footer></main></div>;
}
