import {ChevronDown,SlidersHorizontal} from 'lucide-react'
import {useState} from 'react'
import type {Settings} from '../types'
export function MaterialPanel({value,onChange,disabled}:{value:Settings;onChange:(s:Settings)=>void;disabled:boolean}) {
  const [advanced,setAdvanced]=useState(false), [preset,setPreset]=useState('600x400')
  function change(key:keyof Settings,next:number|string|boolean){onChange({...value,[key]:next})}
  const numberField=(key:'width'|'height'|'thickness'|'kerf'|'gap'|'margin', label:string, min:number,max:number,step:number)=> <label>{label}<div className="unit-input"><input aria-label={label} type="number" min={min} max={max} step={step} required value={Number.isNaN(value[key])?'':value[key]} onChange={e=>change(key,e.target.valueAsNumber)}/><span>mm</span></div></label>
  return <fieldset disabled={disabled} className="material-fields"><div className="section-label"><span>02 / MATERIAL Y CORTE</span><SlidersHorizontal size={13}/></div>
    <label>Formato de lámina<div className="select-wrap"><select value={preset} onChange={e=>{setPreset(e.target.value);if(e.target.value!=='custom'){const [width,height]=e.target.value.split('x').map(Number);onChange({...value,width,height})}}}><option value="600x400">60 × 40 cm · Estándar</option><option value="900x600">90 × 60 cm · Mediana</option><option value="1200x900">120 × 90 cm · Grande</option><option value="custom">Medidas personalizadas</option></select><ChevronDown size={14}/></div></label>
    {preset==='custom'&&<div className="field-row">{numberField('width','Ancho',20,3000,1)}{numberField('height','Alto',20,3000,1)}</div>}
    <div className="field-row">{numberField('thickness','Espesor',0.1,50,0.1)}{numberField('kerf','Kerf',0,3,0.01)}</div><p className="field-help">Compensación de trayectoria: kerf ÷ 2.</p>
    <label>Unidades del archivo<div className="select-wrap"><select value={value.units} onChange={e=>change('units',e.target.value)}><option value="mm">Milímetros (mm)</option><option value="cm">Centímetros (cm)</option><option value="m">Metros (m)</option><option value="in">Pulgadas (in)</option></select><ChevronDown size={14}/></div></label>
    <button type="button" className="advanced-toggle" aria-expanded={advanced} onClick={()=>setAdvanced(!advanced)}>Ajustes de acomodo<ChevronDown size={14} className={advanced?'rotated':''}/></button>
    {advanced&&<div className="advanced-fields"><div className="field-row">{numberField('gap','Separación',0.1,50,0.1)}{numberField('margin','Margen',0,100,0.5)}</div><label className="checkbox-label"><input type="checkbox" checked={value.rotate} onChange={e=>change('rotate',e.target.checked)}/>Permitir giros de 90°</label></div>}
  </fieldset>
}
