import {createClient} from '@supabase/supabase-js'
export const cloudMode = import.meta.env.VITE_APP_MODE === 'cloud' || (import.meta.env.PROD && import.meta.env.VITE_APP_MODE !== 'local')
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
export const supabase = cloudMode && url && key ? createClient(url, key, {
  auth: {persistSession:true, autoRefreshToken:true, detectSessionInUrl:true, flowType:'pkce'},
}) : null
export async function accessToken() {
  if (!cloudMode) return null
  if (!supabase) throw new Error('La autenticación todavía no está configurada.')
  const {data,error} = await supabase.auth.getSession()
  if(error) throw error
  if(!data.session) throw new Error('Inicia sesión para continuar.')
  return data.session.access_token
}
