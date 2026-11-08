import type {Job, Settings} from './types'
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
async function check(response:Response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Error del servidor (${response.status}).`)
  }
  return response
}
export async function processModel(file:File, settings:Settings):Promise<Job> {
  const form = new FormData(); form.append('file', file); form.append('settings', JSON.stringify(settings))
  try { return await check(await fetch(`${BASE}/api/process`, {method:'POST',body:form})).then(r=>r.json()) }
  catch (e) { if (e instanceof TypeError) throw new Error('No se pudo conectar al backend. Inicia FastAPI en el puerto 8000.'); throw e }
}
export async function downloadJob(job:Job, format:string) {
  const response = await check(await fetch(`${BASE}/api/jobs/${job.id}/export/${format}`))
  const blob = await response.blob(); const url = URL.createObjectURL(blob)
  const filename = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] ?? `planar.${format}`
  const a = document.createElement('a'); a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove()
  setTimeout(()=>URL.revokeObjectURL(url), 30000)
}
