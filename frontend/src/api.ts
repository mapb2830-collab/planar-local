import type {Job, Settings} from './types'
import {accessToken} from './auth'
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export async function request(path:string, options:RequestInit={}) {
  const token = await accessToken()
  const headers = new Headers(options.headers)
  if(token) headers.set('Authorization', `Bearer ${token}`)
  let response:Response
  try { response = await fetch(`${BASE}/api${path}`, {...options,headers}) }
  catch { throw new Error('No se pudo conectar con la API. Comprueba la conexión e intenta de nuevo.') }
  if(!response.ok) {
    const data = await response.json().catch(()=>({}))
    throw new Error(typeof data.detail==='string'?data.detail:`No se pudo completar la solicitud (${response.status}).`)
  }
  return response
}
export async function api<T>(path:string, body?:unknown, method=body?'POST':'GET'):Promise<T> {
  const response=await request(path,{method,...(body!==undefined?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})})
  return response.status===204 ? undefined as T : response.json()
}
export async function processModel(file:File, settings:Settings):Promise<Job> {
  const form = new FormData(); form.append('file',file); form.append('settings',JSON.stringify(settings))
  return (await request('/process',{method:'POST',body:form})).json()
}
export async function saveDownload(response:Response, fallback:string) {
  const blob=await response.blob(), url=URL.createObjectURL(blob)
  const filename=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]??fallback
  const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove()
  setTimeout(()=>URL.revokeObjectURL(url),30000)
}
export async function downloadJob(job:Job, format:string) {
  await saveDownload(await request(`/jobs/${job.id}/export/${format}`),`planar.${format}`)
}
