import {useState} from 'react'
import {ArrowUpRight, ArrowRight, Layers3, ScanLine, Box, Eye, EyeOff} from 'lucide-react'
import {Brand} from './Brand'
import type {User} from '../types'
export function Login({onLogin}:{onLogin:(user:User)=>void}) {
  const [register,setRegister]=useState(false), [show,setShow]=useState(false)
  const [email,setEmail]=useState(''), [name,setName]=useState(''), [password,setPassword]=useState('')
  function enter(e:React.FormEvent) {e.preventDefault(); onLogin({name:register?name:email.split('@')[0],email})}
  return <div className="login-page"><section className="login-form-side"><Brand/>
    <div className="login-form-wrap"><div className="eyebrow"><span className="status-dot"/> TU ESTUDIO DE FABRICACIÓN</div>
      <h1>Las buenas ideas<br/>toman <em>forma.</em></h1><p className="login-subtitle">Del modelo digital a tu próxima maqueta.<br/>Un espacio para diseñar, desplegar y fabricar.</p>
      <div className="auth-tabs"><button className={!register?'active':''} onClick={()=>setRegister(false)}>Iniciar sesión</button><button className={register?'active':''} onClick={()=>setRegister(true)}>Crear cuenta</button></div>
      <form onSubmit={enter}>{register&&<label>Nombre<input required autoComplete="name" placeholder="Tu nombre" value={name} onChange={e=>setName(e.target.value)}/></label>}
      <label>Correo electrónico<input type="email" required autoComplete="email" placeholder="nombre@universidad.edu" value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label>Contraseña<div className="password-field"><input required minLength={6} type={show?'text':'password'} autoComplete={register?'new-password':'current-password'} placeholder="Al menos 6 caracteres" value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" className="icon-button" aria-label={show?'Ocultar contraseña':'Mostrar contraseña'} onClick={()=>setShow(!show)}>{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></label>
      <button className="primary auth-submit" type="submit">{register?'Crear mi espacio':'Entrar al estudio'}<ArrowRight size={18}/></button></form>
      <div className="or"><span/>o explora primero<span/></div><button className="demo-login" onClick={()=>onLogin({name:'Estudiante',email:'demo@planar.local'})}>Acceder a la demo<ArrowUpRight size={16}/></button>
      <p className="auth-note">Acceso de demostración. No se crea una cuenta real<br/>ni se guarda tu contraseña.</p>
    </div><footer>DISEÑADO PARA PENSAR CON LAS MANOS.<span>V 0.1 / LOCAL</span></footer>
    </section><section className="login-art"><div className="art-top"><span>EXPLORACIÓN N.º 001</span><span>ESTUDIO DE PLANOS / 2026</span></div>
      <div className="art-title">Una idea.<br/>Infinitas <span>posibilidades.</span></div>
      <svg className="architecture-drawing" viewBox="0 0 680 520" role="img" aria-label="Dibujo axonométrico de una maqueta arquitectónica desmontada"><defs><pattern id="grid" width="38" height="22" patternUnits="userSpaceOnUse" patternTransform="skewY(-30)"><path d="M38 0H0V22" fill="none" stroke="#353e32" strokeWidth="0.6"/></pattern><linearGradient id="face" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#ccdbad"/><stop offset="1" stopColor="#778668"/></linearGradient></defs>
      <path d="M30 340 330 166 650 350 348 522Z" fill="url(#grid)"/>
      <g fill="none" stroke="#647651" strokeDasharray="4 6"><path d="m145 135 0 213m205-331v215m180-119v235M145 348 350 230 530 334 325 452Z"/></g>
      <path d="M145 348 350 230 530 334 325 452Z" fill="#4b5943" stroke="#b1c697"/><path d="m145 348 0 12 180 104 205-118v-12L325 452Z" fill="#738366" stroke="#a2b98b"/>
      <path d="m145 145 205-118v183L145 328Z" fill="url(#face)" stroke="#e0eec8"/><path d="m160 150 175-101v144L160 294Z" fill="#58694b" stroke="#bad29b"/>
      <path d="m160 199 175-101m-135 29v144m44-169v144m44-170v144" stroke="#cbdcaf" strokeWidth="5"/>
      <path d="m370 50 160 93v180l-160-93Z" fill="#83946d" stroke="#d4e3b7"/><path d="m391 87 51 30v104l-51-29Z" fill="#253321" stroke="#bfd29f"/><path d="m459 127 50 30v104l-50-29Z" fill="#253321" stroke="#bfd29f"/>
      <path d="m198 124 152-87 163 94-152 88Z" fill="#caddad" fillOpacity=".1" stroke="#d9fa75"/>
      <path d="m210 309 94-54 94 54-94 54Z" fill="#a4b78c" stroke="#d4e3b7"/><path d="m210 309 0 30 94 54v-30Z" fill="#6d7e5b"/><path d="m304 363 94-54v30l-94 54Z" fill="#415038"/>
      <g stroke="#d9fa75" fill="none"><path d="m105 375 180 104m-186-109 12 10m168 94 12 10M550 354l-205 119m199-124 12 10m-217 109 12 10"/><path d="M570 149v173m-5-173h10m-10 173h10"/></g>
      <g fontFamily="monospace" fontSize="11" fill="#d9fa75"><text x="166" y="449" transform="rotate(30 166 449)">180.00</text><text x="440" y="423" transform="rotate(-30 440 423)">240.00</text><text x="583" y="240" transform="rotate(-90 583 240)">120.00</text><text x="183" y="85">P01</text><text x="503" y="103">P02</text><text x="482" y="386">P03</text></g></svg>
      <div className="art-feature-row"><div><Box size={19}/><span>Importa tu modelo</span></div><i/><div><Layers3 size={19}/><span>Optimiza cada plano</span></div><i/><div><ScanLine size={19}/><span>Llévalo al láser</span></div></div>
      <div className="art-bottom"><span>MENOS DESPERDICIO. MÁS ARQUITECTURA.</span><span>01 — 03</span></div>
    </section></div>
}
