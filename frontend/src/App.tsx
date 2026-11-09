import {useEffect,useRef,useState} from 'react'
import type {Session} from '@supabase/supabase-js'
import {ArrowRight, CreditCard, FolderOpen, History, LayoutDashboard, Loader2, LogOut, ShieldCheck, Sparkles} from 'lucide-react'
import {Login} from './components/Login'
import {Brand} from './components/Brand'
import Studio from './Studio'
import {cloudMode,supabase} from './auth'
import {api} from './api'
import type {Account,Job,User} from './types'
import {Library, HistoryPage, Billing, Admin, Prices} from './pages'

function localUser():User|null {try{return JSON.parse(sessionStorage.getItem('planar-demo-user')??'null')}catch{return null}}
export default function App() {
  const [demo,setDemo]=useState<User|null>(localUser),[session,setSession]=useState<Session|null>(null)
  const [account,setAccount]=useState<Account|null>(null),[loading,setLoading]=useState(cloudMode),[error,setError]=useState('')
  const [path,setPath]=useState(window.location.pathname),[initialFile,setInitialFile]=useState<File|null>(null),[initialJob,setInitialJob]=useState<Job|null>(null),[studioKey,setStudioKey]=useState(0)
  const identityRef=useRef<string|null>(null)
  function navigate(next:string){window.history.pushState({},'',next);setPath(next);window.scrollTo(0,0)}
  useEffect(()=>{const pop=()=>setPath(window.location.pathname);window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop)},[])
  useEffect(()=>{
    if(!cloudMode)return
    if(!supabase){setLoading(false);return}
    let alive=true
    function accept(next:Session|null){
      if(!alive)return
      const id=next?.user.id??null
      if(identityRef.current!==id){identityRef.current=id;setAccount(null);setInitialFile(null);setInitialJob(null);setStudioKey(k=>k+1)}
      setSession(next)
    }
    supabase.auth.getSession().then(({data,error})=>{if(alive){accept(data.session);if(error)setError(error.message);setLoading(false)}}).catch(e=>{if(alive){setError(message(e));setLoading(false)}})
    const {data}=supabase.auth.onAuthStateChange((_event,next)=>accept(next))
    return()=>{alive=false;data.subscription.unsubscribe()}
  },[])
  async function refresh(){const id=identityRef.current;try{const next=await api<Account>('/me');if(id===identityRef.current){setAccount(next);setError('')}}catch(e){if(id===identityRef.current)setError(message(e))}}
  useEffect(()=>{if(session)void refresh()},[session?.user.id])
  function loginLocal(user:User){setDemo(user);try{sessionStorage.setItem('planar-demo-user',JSON.stringify(user))}catch{}}
  async function logout(){if(cloudMode){const result=await supabase?.auth.signOut();if(result?.error){setError(result.error.message);return}setAccount(null);setSession(null);setInitialFile(null);setInitialJob(null);setStudioKey(k=>k+1)}else{sessionStorage.removeItem('planar-demo-user');setDemo(null)}}
  if(!cloudMode)return demo?<Studio user={demo} onLogout={logout}/>:<Login onLogin={loginLocal}/>
  if(loading)return <div className="loading-screen"><Brand/><Loader2 className="spin"/>Abriendo tu espacio…</div>
  if(!session) return path==='/precios'?<div className="public-pricing"><header><Brand/><button className="primary" onClick={()=>navigate('/')}>Entrar al estudio <ArrowRight size={16}/></button></header><Prices/></div>:<Login onLogin={()=>{}} cloud initialError={error} onPrices={()=>navigate('/precios')}/>
  if(path==='/reset-password')return <PasswordReset onDone={()=>navigate('/studio')}/>
  if(!account)return <div className="loading-screen"><Brand/>{error?<><p role="alert">{error}</p><button className="primary" onClick={refresh}>Volver a intentar</button><button className="quiet-button" onClick={logout}>Cerrar sesión</button></>:<><Loader2 className="spin"/><p>Verificando tu cuenta…</p></>}</div>
  const admin=account.role==='owner'||account.role==='admin'
  const route=['/','/studio'].includes(path)?'/studio':path
  const links=[['/studio','Estudio',LayoutDashboard],['/archivos','Archivos',FolderOpen],['/historial','Historial',History],['/precios','Planes',Sparkles],['/cuenta','Mi cuenta',CreditCard],...(admin?[['/admin','Administración',ShieldCheck]]:[])] as [string,string,typeof LayoutDashboard][]
  const openFile=(file:File)=>{setInitialFile(file);setInitialJob(null);setStudioKey(k=>k+1);navigate('/studio')}
  const openJob=(job:Job)=>{setInitialJob(job);setInitialFile(null);setStudioKey(k=>k+1);navigate('/studio')}
  return <div className="cloud-shell"><header className="cloud-header"><a href="/studio" onClick={e=>{e.preventDefault();navigate('/studio')}} aria-label="Planar Studio, inicio"><Brand small/></a><span className="beta-badge">STUDIO / BETA</span><div className="cloud-user"><span className="balance-chip">{account.free_credits} créditos gratis</span><span className="avatar" title={account.email}>{account.name.slice(0,2).toUpperCase()}</span><button className="icon-button" aria-label="Cerrar sesión" onClick={logout}><LogOut size={17}/></button></div></header>
    <nav className="cloud-nav" aria-label="Navegación principal">{links.map(([url,label,Icon])=><a key={url} href={url} aria-current={route===url?'page':undefined} onClick={e=>{if(!e.ctrlKey&&!e.metaKey){e.preventDefault();navigate(url)}}}><Icon size={16}/>{label}</a>)}<span><span className="status-dot"/>Pagos reales desactivados</span></nav>
    {error&&<div className="alert error" role="alert">{error}</div>}
    <div hidden={route!=='/studio'}><Studio key={studioKey} user={account} cloud onLogout={logout} onProcessed={refresh} initialFile={initialFile} initialJob={initialJob}/></div>
    {route==='/archivos'&&<Library onOpen={openFile} onChange={refresh}/>}
    {route==='/historial'&&<HistoryPage onOpen={openJob}/>}
    {route==='/precios'&&<Prices/>}
    {route==='/cuenta'&&<Billing account={account} onChange={refresh}/>}
    {route==='/admin'&&(admin?<Admin account={account} onChange={refresh}/>:<PageDenied/>)}
    {!['/studio','/archivos','/historial','/precios','/cuenta','/admin'].includes(route)&&<main className="page-content"><h1>Esta página no existe.</h1><button className="primary" onClick={()=>navigate('/studio')}>Volver al estudio</button></main>}
  </div>
}
export function message(error:unknown){return error instanceof Error?error.message:'No se pudo completar la operación.'}
function PageDenied(){return <main className="page-content"><ShieldCheck size={36}/><h1>Acceso restringido</h1><p>El propietario debe asignarte permisos de administración.</p></main>}
function PasswordReset({onDone}:{onDone:()=>void}){
  const [password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  return <main className="reset-page"><Brand/><h1>Una nueva contraseña.</h1><form onSubmit={async e=>{e.preventDefault();setBusy(true);const result=await supabase!.auth.updateUser({password});setBusy(false);if(result.error)setError(result.error.message);else onDone()}}><label>Nueva contraseña<input type="password" minLength={12} required autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}/></label><p role="alert">{error}</p><button className="primary" disabled={busy}>Guardar contraseña</button></form></main>
}
