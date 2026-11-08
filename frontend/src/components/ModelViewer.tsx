import {Component, Suspense, useEffect,useMemo,useState} from 'react'
import type {ReactNode} from 'react'
import {Canvas} from '@react-three/fiber'
import {Bounds, Edges, Grid, OrbitControls, GizmoHelper, GizmoViewport, Center, ContactShadows} from '@react-three/drei'
import * as THREE from 'three'
import {Box, RotateCcw, Scan, AlertTriangle} from 'lucide-react'
import type {Job} from '../types'
class ViewerBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  render(){return this.state.failed?<div className="empty-state"><AlertTriangle/><h3>Vista 3D no disponible</h3><p>Activa WebGL o prueba otro navegador.<br/>El despiece y las descargas siguen disponibles.</p></div>:this.props.children}
}
function LoadedMesh({preview,wire}:{preview:Job['preview'];wire:boolean}) {
  const geometry=useMemo(()=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(preview.vertices,3));g.setIndex(preview.faces);g.computeVertexNormals();return g},[preview])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <group rotation={[-Math.PI/2,0,0]}><mesh geometry={geometry} castShadow receiveShadow><meshStandardMaterial color="#cbd4bc" metalness={0.1} roughness={0.7} side={THREE.DoubleSide} wireframe={wire}/>{!wire&&<Edges threshold={12} color="#3c4a34"/>}</mesh></group>
}
function Sample({wire}:{wire:boolean}) {
  return <group><mesh position={[0,.08,0]} receiveShadow castShadow><boxGeometry args={[3.5,.16,2.8]}/><meshStandardMaterial color="#7a876b" wireframe={wire}/><Edges color="#b4c49c"/></mesh>{[-1.2,0,1.2].map(x=><mesh key={x} position={[x,1,0]} castShadow receiveShadow><boxGeometry args={[.08,1.8,2.2]}/><meshStandardMaterial color="#ccd7b7" wireframe={wire}/><Edges color="#5b684d"/></mesh>)}<mesh position={[0,1.95,0]} castShadow><boxGeometry args={[3.2,.08,2.4]}/><meshStandardMaterial color="#bbcba0" transparent opacity={.8} wireframe={wire}/><Edges color="#5b684d"/></mesh></group>
}
export function ModelViewer({job,busy}:{job:Job|null;busy:boolean}) {
  const [wire,setWire]=useState(false), [reset,setReset]=useState(0)
  const extent=job?Math.max(...job.preview.bounds,1):4
  return <section className="viewer-panel model-panel"><div className="panel-heading"><div><Box size={16}/><h2>Modelo 3D</h2><span className="badge">{job?'ORIGINAL':'EJEMPLO'}</span></div><div className="panel-actions"><button title="Alternar malla" aria-label="Alternar malla" aria-pressed={wire} className={`icon-button ${wire?'active':''}`} onClick={()=>setWire(!wire)}><Scan size={16}/></button><button title="Restablecer cámara" aria-label="Restablecer cámara" className="icon-button" onClick={()=>setReset(reset+1)}><RotateCcw size={15}/></button></div></div>
    <div className="model-canvas"><span className="viewport-label">PERSPECTIVA <span> / </span> {wire?'WIREFRAME':'SOMBREADO'}</span><ViewerBoundary><Suspense fallback={<div className="empty-state">Preparando visor…</div>}><Canvas key={`${job?.id??'sample'}-${reset}`} shadows camera={{position:[extent,extent*.8,extent], fov:40, near:.01,far:100000}} dpr={[1,1.7]} gl={{antialias:true}} fallback={<div className="empty-state">Tu navegador no admite WebGL.</div>}><color attach="background" args={['#1b201e']}/><ambientLight intensity={1.4}/><directionalLight position={[extent,extent*2,extent]} intensity={2.8} castShadow shadow-mapSize={[1024,1024]} shadow-camera-left={-extent} shadow-camera-right={extent} shadow-camera-top={extent} shadow-camera-bottom={-extent} shadow-camera-far={extent*5}/><Bounds fit clip observe margin={1.35}><Center top>{job?<LoadedMesh preview={job.preview} wire={wire}/>:<Sample wire={wire}/>}</Center></Bounds><Grid position={[0,-.01,0]} args={[extent*6,extent*6]} cellSize={extent/12} sectionSize={extent/3} cellColor="#303a32" sectionColor="#455142" fadeDistance={extent*5} infiniteGrid/><ContactShadows position={[0,-.02,0]} opacity={.3} scale={extent*3} blur={2.5} far={extent*2} resolution={256} frames={1}/><OrbitControls makeDefault minDistance={extent*.05} maxDistance={extent*8}/><GizmoHelper alignment="bottom-right" margin={[50,50]}><GizmoViewport axisColors={['#b77671','#9cb87e','#7796b8']} labelColor="white" hideNegativeAxes/></GizmoHelper></Canvas></Suspense></ViewerBoundary>{busy&&<div className="canvas-busy"><span className="spinner"/>Procesando geometría…</div>}<div className="viewport-hint">Arrastrar para orbitar <b>·</b> Rueda para zoom <b>·</b> Clic derecho para mover</div></div>
    <div className="panel-footer"><span><span className="status-dot muted"/>{job?job.filename:'Pabellón conceptual · vista de ejemplo'}</span><span>{job?`${job.preview.bounds.map(n=>n.toFixed(1)).join(' × ')} mm`:'Z ↑'}</span></div>
  </section>
}
