import {beforeEach,describe,expect,it,vi} from 'vitest'
import {render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import {Login} from '../components/Login'
import {Admin,Billing,Prices} from '../pages'
import type {Account} from '../types'

const mocks=vi.hoisted(()=>({api:vi.fn(),getSession:vi.fn(),signUp:vi.fn(),signInWithPassword:vi.fn(),resetPasswordForEmail:vi.fn()}))
vi.mock('../auth',()=>({cloudMode:true,supabase:{auth:{getSession:mocks.getSession,signUp:mocks.signUp,signInWithPassword:mocks.signInWithPassword,resetPasswordForEmail:mocks.resetPasswordForEmail,onAuthStateChange:()=>({data:{subscription:{unsubscribe:vi.fn()}}})}}}))
vi.mock('../api',()=>({api:mocks.api,request:vi.fn(),saveDownload:vi.fn(),processModel:vi.fn(),downloadJob:vi.fn()}))
vi.mock('../components/ModelViewer',()=>({ModelViewer:()=> <div>Visor de prueba</div>}))
const account:Account={id:'user-id',email:'ana@example.test',name:'Ana',role:'user',free_credits:5,trial_credits:100,paid_credits:0,storage_bytes:0,file_count:0,subscription:null}
beforeEach(()=>{vi.clearAllMocks();window.history.replaceState({},'','/');mocks.getSession.mockResolvedValue({data:{session:null},error:null});mocks.api.mockResolvedValue(account);mocks.signUp.mockResolvedValue({data:{session:null},error:null});mocks.signInWithPassword.mockResolvedValue({data:{session:null},error:null})})

describe('cloud accounts and commercial restrictions',()=>{
  it('registers through the identity provider and requires email confirmation',async()=>{
    render(<Login cloud onLogin={vi.fn()}/>);const u=userEvent.setup()
    await u.click(screen.getByRole('button',{name:'Crear cuenta'}));await u.type(screen.getByLabelText('Nombre'),'Ana')
    await u.type(screen.getByLabelText('Correo electrónico'),account.email);await u.type(screen.getByLabelText('Contraseña'),'a-long-test-password')
    await u.click(screen.getByRole('button',{name:'Crear mi espacio'}))
    expect(mocks.signUp).toHaveBeenCalledWith(expect.objectContaining({email:account.email,options:expect.objectContaining({data:{name:'Ana'}})}))
    expect(await screen.findByRole('status')).toHaveTextContent('confirma tu cuenta')
    expect(screen.queryByRole('button',{name:/Acceder a la demo/})).not.toBeInTheDocument()
    expect(sessionStorage.getItem('planar-demo-user')).toBeNull()
  })
  it('shows identity errors without entering the studio',async()=>{
    mocks.signInWithPassword.mockResolvedValue({error:new Error('Correo o contraseña incorrectos')})
    render(<Login cloud onLogin={vi.fn()}/>);const u=userEvent.setup()
    await u.type(screen.getByLabelText('Correo electrónico'),account.email);await u.type(screen.getByLabelText('Contraseña'),'a-long-test-password')
    await u.click(screen.getByRole('button',{name:'Entrar al estudio'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('incorrectos')
  })
  it('keeps every real purchase disabled and marks simulations',()=>{
    render(<Prices/>);for(const button of screen.getAllByRole('button'))expect(button).toBeDisabled()
    expect(screen.getByText(/No se realizan cobros/)).toBeInTheDocument()
    expect(screen.getByText(/No generan créditos pagados/)).toBeInTheDocument()
  })
  it('denies a direct admin route for an ordinary verified user',async()=>{
    mocks.getSession.mockResolvedValue({data:{session:{user:{id:account.id}}}})
    window.history.replaceState({},'','/admin');render(<App/>)
    expect(await screen.findByRole('heading',{name:'Acceso restringido'})).toBeInTheDocument()
    expect(screen.queryByRole('link',{name:'Administración'})).not.toBeInTheDocument()
    expect(mocks.api).not.toHaveBeenCalledWith('/admin')
  })
  it('labels balances so simulated credits cannot be mistaken for paid credits',async()=>{
    mocks.api.mockResolvedValue([]);render(<Billing account={account} onChange={vi.fn()}/>);
    expect(screen.getByText('Solo pruebas · no utilizables para procesar')).toBeInTheDocument()
    expect(screen.getByText('Pagos reales desactivados')).toBeInTheDocument()
    await waitFor(()=>expect(mocks.api).toHaveBeenCalledWith('/credits'))
  })
  it('submits an explicit admin simulation with a unique request ID',async()=>{
    const data={users:[account],audit:[],settings:{registration_open:true},jobs_count:0}
    mocks.api.mockResolvedValue(data);render(<Admin account={{...account,role:'owner'}} onChange={vi.fn()}/>);const u=userEvent.setup()
    await u.selectOptions(await screen.findByLabelText('Cuenta verificada'),account.id)
    await u.click(screen.getByRole('button',{name:'Registrar compra simulada'}))
    expect(mocks.api).toHaveBeenCalledWith('/admin/simulations',expect.objectContaining({user_id:account.id,credits:25,plan:'pro',request_id:expect.any(String)}))
    expect(await screen.findByText(/Compra simulada registrada/)).toBeInTheDocument()
  })
})
