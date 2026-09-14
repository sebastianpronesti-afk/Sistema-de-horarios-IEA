import React,{useEffect,useState} from 'react';
import {EditKey,saveAcademic} from './AcademicEditors';

async function read(path,signal){
  const response=await fetch(path,{signal});const data=await response.json().catch(()=>null);
  if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:'No se pudo cargar la planificación');
  return data;
}
function AssignmentEditor({period,plan,subject,campuses,onSaved,onClose,existing,catalogRevision,offerRevision}){
  const [form,setForm]=useState({docente_id:existing?.docente_id||'',dia:existing?.dia||'Lunes',
    hora_inicio:existing?.hora_inicio||'',hora_fin:existing?.hora_fin||'',sede_id:existing?.sede_id||'',
    modalidad:existing?.modalidad||'presencial',comision:existing?.comision||''});
  const [teachers,setTeachers]=useState([]),[candidates,setCandidates]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const prefix='/api/planificacion/'+period+'/planes/'+plan+'/materias/'+subject.id;
  useEffect(()=>{let active=true;const c=new AbortController();read('/api/docentes',c.signal).then(d=>{if(active)setTeachers(d);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;c.abort();};},[]);
  const set=(key,value)=>{setForm({...form,[key]:value});if(['modalidad','sede_id'].includes(key)){setCandidates([]);setMessage('');}};
  const suggest=async()=>{setBusy(true);setError('');setCandidates([]);try{const q=new URLSearchParams({modalidad:form.modalidad});if(form.sede_id)q.set('sede_id',form.sede_id);const data=await read(prefix+'/sugerencias?'+q);setCandidates(data.candidatos);setMessage(data.motivo||'Opciones ordenadas por carga docente actual. Elegí una para completar el formulario.');}catch(e){setError(e.message);}finally{setBusy(false);}};
  const save=async()=>{setBusy(true);setError('');try{
    const previous=existing?Object.fromEntries(['docente_id','dia','hora_inicio','hora_fin','sede_id','modalidad','comision'].map(k=>[k,existing[k]??null])):undefined;
    await saveAcademic(prefix+'/asignar',{...form,docente_id:Number(form.docente_id),sede_id:form.sede_id?Number(form.sede_id):null,asignacion_id:existing?.id,previous,catalog_revision:catalogRevision,oferta_revision:offerRevision});onSaved();
  }catch(e){setError(e.message);}finally{setBusy(false);}};
  return <section role="dialog" aria-label="Asignar horario" className="border rounded bg-slate-50 p-5 my-4">
    <h3 className="text-xl font-bold">{existing?'Editar clase':'Asignar clase'} · {subject.nombre}</h3>
    <div className="grid md:grid-cols-3 gap-3 my-3">
      <label>Modalidad<select className="border p-2 block w-full" value={form.modalidad} onChange={e=>set('modalidad',e.target.value)}><option value="presencial">Presencial</option><option value="virtual_tm">Virtual · mañana</option><option value="virtual_tn">Virtual · noche</option></select></label>
      <label>Sede<select className="border p-2 block w-full" value={form.sede_id} onChange={e=>set('sede_id',e.target.value)}><option value="">Sin sede física</option>{campuses.map(s=><option key={s.id} value={s.id}>{s.nombre}</option>)}</select></label>
      <label>Comisión<input className="border p-2 block w-full" value={form.comision} onChange={e=>set('comision',e.target.value)}/></label>
    </div>
    <button disabled={busy} onClick={suggest} className="bg-slate-800 text-white px-4 py-2 rounded">Buscar sugerencias disponibles</button>
    <p role="status">{message}</p>
    <div className="max-h-60 overflow-auto my-3">{candidates.map((c,i)=><button key={i} className="block border rounded p-2 my-1 w-full text-left" onClick={()=>setForm({...form,...c})}>{c.docente} · {c.dia} {c.hora_inicio}–{c.hora_fin} · {(c.minutos_asignados/60).toFixed(1)} h asignadas</button>)}</div>
    <div className="grid md:grid-cols-4 gap-3">
      <label>Docente<select className="border p-2 block w-full" value={form.docente_id} onChange={e=>set('docente_id',e.target.value)}><option value="">Elegí docente</option>{teachers.map(d=><option key={d.id} value={d.id}>{d.apellido}, {d.nombre}</option>)}</select></label>
      <label>Día<select className="border p-2 block w-full" value={form.dia} onChange={e=>set('dia',e.target.value)}>{['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'].map(d=><option key={d}>{d}</option>)}</select></label>
      <label>Inicio<input className="border p-2 block w-full" type="time" value={form.hora_inicio} onChange={e=>set('hora_inicio',e.target.value)}/></label>
      <label>Fin<input className="border p-2 block w-full" type="time" value={form.hora_fin} onChange={e=>set('hora_fin',e.target.value)}/></label>
    </div><EditKey/>{error&&<p role="alert" className="text-red-700">{error}</p>}
    <button disabled={busy} onClick={save} className="bg-blue-700 text-white rounded px-4 py-2">Guardar clase</button> <button disabled={busy} onClick={onClose}>Cancelar</button>
    <p className="text-sm mt-3">Al guardar se vuelven a comprobar demanda, habilitación, disponibilidad y cruces. La clase se comparte con todos los planes vinculados a esta cátedra.</p>
  </section>;
}
export default function CurriculumPlanning({cuatrimestre,puedeEditar=false,onCatalog,onSaved}){
  const [catalog,setCatalog]=useState(null),[campuses,setCampuses]=useState([]),[selected,setSelected]=useState('');
  const [data,setData]=useState(null),[error,setError]=useState(''),[attempt,setAttempt]=useState(0),[configuring,setConfiguring]=useState(false);
  const [selectedSubjects,setSelectedSubjects]=useState([]),[editor,setEditor]=useState(null),[busy,setBusy]=useState(false);
  useEffect(()=>{let active=true;const controller=new AbortController();Promise.all([read('/api/planes-estudio',controller.signal),read('/api/sedes',controller.signal)]).then(([c,s])=>{if(active){setCatalog(c);setCampuses(s);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;controller.abort();};},[]);
  useEffect(()=>{setData(null);setEditor(null);setConfiguring(false);if(!selected)return;let active=true;const controller=new AbortController();setError('');read('/api/planificacion/'+cuatrimestre+'/planes/'+selected,controller.signal).then(d=>{if(active){setData(d);setSelectedSubjects(d.materias.filter(s=>s.ofertada).map(s=>s.id));}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;controller.abort();};},[selected,cuatrimestre,attempt]);
  const saveOffer=async()=>{setBusy(true);setError('');try{await saveAcademic('/api/planificacion/'+cuatrimestre+'/planes/'+selected+'/oferta',{revision:data.oferta_revision,catalog_revision:data.revision,materia_ids:selectedSubjects},'PUT');setAttempt(a=>a+1);}catch(e){setError(e.message);}finally{setBusy(false);}};
  const plans=(catalog?.careers||[]).flatMap(c=>c.planes.map(p=>({...p,carrera:c.nombre})));
  const rows=(data?.materias||[]).filter(s=>configuring||s.ofertada).sort((a,b)=>(a.anio??99)-(b.anio??99)||(a.cuatrimestre??99)-(b.cuatrimestre??99));
  return <div className="academic-catalog">
    <h2 className="text-2xl font-bold">Horarios por carrera y plan</h2>
    <p>Cátedras → plan de estudios → inscriptos del período → apertura y disponibilidad docente.</p>
    <label className="block my-4">Carrera y versión del plan<select aria-label="Carrera y versión del plan" className="border rounded p-3 block w-full" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Elegí un plan</option>{plans.map(p=><option key={p.id} value={p.id}>{p.carrera} · {p.etiqueta} · {p.jurisdiccion||'Jurisdicción pendiente'} · {p.resolucion||'Resolución pendiente'}</option>)}</select></label>
    {!catalog&&!error&&<p role="status">Cargando planes…</p>}
    {error&&<p role="alert" className="text-red-700">{error} <button onClick={()=>setAttempt(a=>a+1)}>Reintentar</button></p>}
    {selected&&!data&&!error&&<p role="status">Cargando oferta del período…</p>}
    {data&&<>
      <p className="bg-blue-50 p-3 my-3">{data.alcance_inscriptos}</p>
      {puedeEditar&&<button className="bg-slate-800 text-white px-4 py-2 rounded my-2" onClick={()=>setConfiguring(!configuring)}>{configuring?'Volver a horarios':'Configurar materias de este período'}</button>}
      <button className="ml-3 text-blue-700 underline" onClick={onCatalog}>Abrir planes de estudio completos</button>
      {configuring&&<><p>Elegí las materias a ofrecer. El año y cuatrimestre del plan no se deducen del calendario del período.</p><EditKey/><button disabled={busy} onClick={saveOffer} className="bg-blue-700 text-white rounded px-4 py-2 my-3">Guardar oferta del período</button></>}
      {editor&&<AssignmentEditor key={editor.subject.id+':'+(editor.existing?.id||'new')} period={cuatrimestre} plan={selected} subject={editor.subject} existing={editor.existing} catalogRevision={data.revision} offerRevision={data.oferta_revision} campuses={campuses} onSaved={()=>{setEditor(null);setAttempt(a=>a+1);onSaved?.();}} onClose={()=>setEditor(null)}/>}
      <div className="academic-table-wrap"><table className="academic-table"><thead><tr>{configuring&&<th>Ofrecer</th>}<th>Año</th><th>Cuatrimestre del plan</th><th>Materia y cátedra</th><th>Inscriptos de la cátedra</th><th>Apertura</th><th>Clases del período</th></tr></thead>
      <tbody>{rows.map(s=><tr key={s.id}>
        {configuring&&<td><input aria-label={'Ofrecer '+s.nombre} type="checkbox" checked={selectedSubjects.includes(s.id)} disabled={!s.catedra||!s.anio||!s.cuatrimestre} onChange={e=>setSelectedSubjects(e.target.checked?[...selectedSubjects,s.id]:selectedSubjects.filter(id=>id!==s.id))}/></td>}
        <td>{s.anio||'Pendiente'}</td><td>{s.cuatrimestre||'Pendiente'}</td><td><strong>{s.nombre}</strong><p>{s.catedra?s.catedra.codigo+' · '+s.catedra.nombre:'Confirmá la cátedra en el plan'}</p></td>
        <td>{s.inscriptos??'Sin asociación'}</td><td>{s.criterio}{s.docentes_requeridos>0&&<p>{s.docentes_requeridos} docente(s) según el criterio institucional</p>}</td>
        <td>{s.asignaciones.map(a=><div key={a.id} className="mb-2"><p>{a.docente||'Docente pendiente'} · {a.dia||'Día pendiente'} {a.hora_inicio}–{a.hora_fin||'Fin pendiente'} {a.comision&&'· '+a.comision}</p>{puedeEditar&&s.ofertada&&<button className="text-blue-700 underline" onClick={()=>setEditor({subject:s,existing:a})}>Editar clase</button>}</div>)}
          {puedeEditar&&s.ofertada&&s.criterio==='ABRIR'&&<button className="text-blue-700 underline" onClick={()=>setEditor({subject:s})}>Asignar o buscar sugerencias</button>}</td>
      </tr>)}</tbody></table></div>
      {!rows.length&&<p className="academic-empty">Este plan todavía no tiene materias configuradas para el período. Completá sus asociaciones y seleccioná la oferta.</p>}
      <p className="mt-4">Las cátedras compartidas muestran las mismas clases en sus distintos planes; no se crean copias por carrera.</p>
    </>}
  </div>;
}
