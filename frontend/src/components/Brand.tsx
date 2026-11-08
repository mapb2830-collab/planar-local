export function Brand({small=false}:{small?:boolean}) {
  return <div className={`brand ${small?'small':''}`}><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M8 31V9h15l9 11-9 11Z"/><path d="M8 20h24M23 9v22"/></svg><span>PLANAR<span className="brand-dot">.</span></span></div>
}
