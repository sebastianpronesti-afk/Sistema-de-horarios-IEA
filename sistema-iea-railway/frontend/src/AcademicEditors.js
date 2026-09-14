import React,{useEffect,useState} from 'react';
let sessionKey='';
export function rememberEditorKey(value){sessionKey=value;}
export function EditKey(){
  const [value,setValue]=useState(sessionKey);
  return <label className="block my-3">Clave de edición para guardar<input type="password" autoComplete="current-password" className="border rounded p-2 block w-full" value={value} onChange={e=>{setValue(e.target.value);sessionKey=e.target.value;}}/></label>;
}
export async function saveAcademic(path,data,method='POST'){
  if(!sessionKey)throw new Error('Ingresá la clave de edición para guardar');
  const response=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,clave_edicion:sessionKey})});
  const result=await response.json().catch(()=>null);
  if(!response.ok)throw new Error(typeof result?.detail==='string'?result.detail:'No se pudo guardar el cambio');
  return result;
}
function TextField({label,value,onChange,type='text'}){
  return <label className="block">{label}<input type={type} value={value??''} onChange={e=>onChange(e.target.value)} className="border rounded p-2 block w-full"/></label>;
}
export function PlanEditor({plan,revision,onSaved,onClose}){
  const fields={etiqueta:'Identificación del plan',nombre_oficial:'Nombre oficial',resolucion:'Resolución',jurisdiccion:'Jurisdicción',titulo:'Título otorgado',nota_vigencia:'Observaciones de vigencia'};
  const [form,setForm]=useState(()=>Object.fromEntries([...Object.keys(fields),'modalidad','situacion','inicio_informado'].map(k=>[k,plan[k]??''])));
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const set=(key,value)=>setForm({...form,[key]:value});
  const save=async()=>{setBusy(true);setError('');try{await saveAcademic('/api/planes-estudio/editar',{operation:'plan',plan_id:plan.id,revision,changes:{...form,inicio_informado:form.inicio_informado===''?null:Number(form.inicio_informado)}});onSaved();}catch(e){setError(e.message);}finally{setBusy(false);}};
  return <section role="dialog" aria-label="Editar plan" className="bg-slate-50 border rounded p-5 my-4">
    <h3 className="font-bold text-xl">Editar información del plan</h3><div className="grid md:grid-cols-2 gap-3">{Object.entries(fields).map(([k,label])=><TextField key={k} label={label} value={form[k]} onChange={v=>set(k,v)}/>)}
    <label>Modalidad<select className="border rounded p-2 block w-full" value={form.modalidad} onChange={e=>set('modalidad',e.target.value)}><option value="">Por confirmar</option><option value="presencial">Presencial</option><option value="distancia">A distancia</option></select></label>
    <label>Situación<select className="border rounded p-2 block w-full" value={form.situacion} onChange={e=>set('situacion',e.target.value)}>{Object.entries({por_confirmar:'Por confirmar',vigente_informado:'Vigente informado',anterior:'Anterior',no_ofertado:'No ofertado',futuro:'Futuro'}).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
    <TextField label="Año de inicio informado" type="number" value={form.inicio_informado} onChange={v=>set('inicio_informado',v)}/></div>
    <EditKey/>{error&&<p role="alert">{error}</p>}<button disabled={busy} onClick={save} className="bg-blue-700 text-white rounded px-4 py-2">Guardar plan</button> <button disabled={busy} onClick={onClose}>Cancelar</button>
  </section>;
}
export function SubjectEditor({subject,plan,career,revision,onSaved,onClose}){
  const moving=!!career;
  const [target,setTarget]=useState(plan?.id||''),[targetPlan,setTargetPlan]=useState(plan||null);
  const [chairs,setChairs]=useState([]),[query,setQuery]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({nombre:subject.nombre||'',anio:subject.anio??'',cuatrimestre:subject.cuatrimestre??'',
    catedra_id:subject.catedra_id??subject.vinculo?.catedra?.id??'',correlativa_ids:subject.correlativa_ids||[],revision_nota:subject.revision_nota||''});
  useEffect(()=>{let active=true;const controller=new AbortController();fetch('/api/planes-estudio/opciones',{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('No se pudo cargar el catálogo de cátedras');return r.json();}).then(d=>{if(!Array.isArray(d.catedras))throw Error('Catálogo de cátedras incompleto');if(active)setChairs(d.catedras);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;controller.abort();};},[]);
  useEffect(()=>{if(!moving)return;setTargetPlan(null);if(!target)return;let active=true;const controller=new AbortController();fetch('/api/planes-estudio/'+target,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('No se pudo cargar el plan elegido');return r.json();}).then(d=>{if(active)setTargetPlan(d);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;controller.abort();};},[moving,target]);
  const set=(key,value)=>setForm({...form,[key]:value});
  const save=async()=>{setBusy(true);setError('');try{
    const changes={...form,anio:form.anio===''?null:Number(form.anio),cuatrimestre:form.cuatrimestre===''?null:Number(form.cuatrimestre),catedra_id:form.catedra_id===''?null:Number(form.catedra_id)};
    await saveAcademic('/api/planes-estudio/editar',{operation:moving?'move':subject.id?'subject':'new_subject',revision,plan_id:target,career_id:career?.id,subject_id:subject.id,changes});onSaved();
  }catch(e){setError(e.message);}finally{setBusy(false);}};
  const visible=chairs.filter(c=>String(c.id)===String(form.catedra_id)||[c.codigo,c.nombre].join(' ').toLowerCase().includes(query.toLowerCase()));
  return <section role="dialog" aria-label="Editar materia" className="bg-slate-50 border rounded p-5 my-4">
    <h3 className="font-bold text-xl">{moving?'Asignar materia pendiente a un plan':'Editar materia del plan'}</h3>
    {moving&&<label>Plan de destino<select className="border rounded p-2 block w-full" value={target} onChange={e=>{setTarget(e.target.value);set('correlativa_ids',[]);}}><option value="">Elegí un plan de esta carrera</option>{career.planes.map(p=><option key={p.id} value={p.id}>{p.etiqueta} · {p.resolucion||'Resolución pendiente'}</option>)}</select></label>}
    <div className="grid md:grid-cols-3 gap-3"><TextField label="Materia del plan" value={form.nombre} onChange={v=>set('nombre',v)}/><TextField label="Año académico" type="number" value={form.anio} onChange={v=>set('anio',v)}/><TextField label="Cuatrimestre académico" type="number" value={form.cuatrimestre} onChange={v=>set('cuatrimestre',v)}/></div>
    <label className="block my-3">Buscar cátedra<input className="border rounded p-2 block w-full" type="search" value={query} onChange={e=>setQuery(e.target.value)}/></label>
    <label>Cátedra asociada<select className="border rounded p-2 block w-full" value={form.catedra_id} onChange={e=>set('catedra_id',e.target.value)}><option value="">Sin asociación confirmada</option>{visible.map(c=><option key={c.id} value={c.id}>{c.codigo} · {c.nombre}</option>)}</select></label>
    <fieldset className="my-3"><legend className="font-bold">Correlatividades dentro de este plan</legend>
      <p>Seleccioná las materias requeridas. Ninguna selección significa que no tiene correlatividades.</p>
      <div className="max-h-60 overflow-auto border rounded p-3">{(targetPlan?.materias||[]).filter(s=>s.id!==subject.id).map(s=><label key={s.id} className="block"><input type="checkbox" checked={form.correlativa_ids.includes(s.id)} onChange={e=>set('correlativa_ids',e.target.checked?[...form.correlativa_ids,s.id]:form.correlativa_ids.filter(id=>id!==s.id))}/> {s.nombre}</label>)}</div>
      {subject.correlatividades&&<details><summary>Texto del archivo de origen</summary><p>{subject.correlatividades}</p></details>}
    </fieldset>
    <TextField label="Nota de la revisión" value={form.revision_nota} onChange={v=>set('revision_nota',v)}/>
    <EditKey/>{error&&<p role="alert" className="text-red-700">{error}</p>}
    <button disabled={busy||!target||!targetPlan} className="bg-blue-700 text-white rounded px-4 py-2" onClick={save}>Guardar materia</button> <button disabled={busy} onClick={onClose}>Cancelar</button>
  </section>;
}
