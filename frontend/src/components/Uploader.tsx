import {useRef,useState} from 'react'
import {UploadCloud, FileBox, X, FlaskConical} from 'lucide-react'
const allowed = /\.(stl|obj|dxf|3dm|ply|off)$/i
export function Uploader({file,disabled,onFile,onDemo,onError}:{file:File|null;disabled:boolean;onFile:(file:File|null)=>void;onDemo:()=>void;onError:(error:string)=>void}) {
  const input=useRef<HTMLInputElement>(null), [drag,setDrag]=useState(false)
  function choose(file?:File) {if(!file)return; if(!allowed.test(file.name))return onError('Usa un archivo STL, OBJ, DXF, 3DM, PLY u OFF.'); if(file.size>20*1024*1024)return onError('El archivo debe pesar menos de 20 MB.');if(!file.size)return onError('El archivo está vacío.');onFile(file)}
  return <div><div className="section-label"><span>01 / MODELO DE ORIGEN</span><span>20 MB MÁX.</span></div>
    <input ref={input} type="file" accept=".stl,.obj,.dxf,.3dm,.ply,.off" hidden disabled={disabled} onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
    {file?<div className="selected-file"><div className="file-icon"><FileBox size={22}/></div><div><strong title={file.name}>{file.name}</strong><small>{(file.size/1024).toFixed(1)} KB · LISTO PARA PROCESAR</small></div><button disabled={disabled} className="icon-button" aria-label="Quitar archivo" onClick={()=>onFile(null)}><X size={16}/></button></div>:<button disabled={disabled} className={`dropzone ${drag?'dragging':''}`} onClick={()=>input.current?.click()} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);if(!disabled)choose(e.dataTransfer.files[0])}}><span className="upload-icon"><UploadCloud size={23}/></span><strong>Tu próximo proyecto,<br/>empieza aquí.</strong><span>Arrastra un archivo o <u>explora</u></span><small>STL · OBJ · DXF · 3DM · PLY · OFF</small></button>}
    <button className="example-button" disabled={disabled} onClick={onDemo}><FlaskConical size={14}/>Probar con un pabellón de ejemplo<span>↗</span></button>
  </div>
}
