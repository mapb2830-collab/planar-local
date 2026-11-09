import {defineConfig,loadEnv} from 'vite'
import process from 'node:process'
import {Buffer} from 'node:buffer'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({command,mode})=>{
  const env={...loadEnv(mode,process.cwd(),''),...process.env}
  if(command==='build'&&(env.VITE_APP_MODE!=='local'||env.VERCEL)){
    if(env.VITE_APP_MODE==='local')throw new Error('Vercel cannot deploy offline/demo authentication.')
    for(const name of ['VITE_API_URL','VITE_SUPABASE_URL']){
      let url:URL
      try{url=new URL(env[name]??'')}catch{throw new Error(`${name} is required for a cloud build.`)}
      if(url.protocol!=='https:'||['localhost','127.0.0.1','[::1]'].includes(url.hostname)||url.pathname!=='/'||url.search||url.hash||url.username)
        throw new Error(`${name} must be a public HTTPS origin without a path.`)
    }
    const key=env.VITE_SUPABASE_PUBLISHABLE_KEY??''
    let anonymous=false
    try{anonymous=JSON.parse(Buffer.from(key.split('.')[1],'base64url').toString()).role==='anon'}catch{/* Modern publishable keys are not JWTs. */}
    if(!key.startsWith('sb_publishable_')&&!anonymous)throw new Error('Use a Supabase publishable/anon key, never a service-role or secret key.')
  }
  return {plugins:[react(),tailwindcss()],server:{port:5173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000'}},
    build:{rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules/three/'))return 'three-engine'}}}}}
})
