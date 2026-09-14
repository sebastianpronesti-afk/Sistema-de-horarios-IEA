import React,{useEffect,useState} from 'react';
import {EditKey,saveAcademic} from './AcademicEditors';

async function read(url,signal){
  const r=await fetch(url,{signal}),data=await r.json().catch(()=>null);
  if(!r.ok)throw Error(typeof data?.detail==='string'?data.detail:'No se pudieron cargar las inscripciones');
  return data;
}

function StudentPlan({row,plans,period,catalogRevision,puedeEditar,onSaved}){
  const [plan,setPlan]=useState(row.plan_id||''),[note,setNote]=useState(row.nota||'');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const save=async()=>{setBusy(true);setError('');try{
    await saveAcademic(`/api/inscripciones-planes/${period}/cursos/${row.curso_id}/alumnos/${row.alumno_id}`,{
      revision:row.revision,course_revision:row.course_revision,catalog_revision:catalogRevision,
      source_token:row.source_token,plan_id:plan||null,nota:note
    },'PUT');onSaved();
  }catch(e){setError(e.message);}finally{setBusy(false);}};
  const label=p=>`${p.etiqueta} · ${p.resolucion||'Resolución pendiente'} · ${p.jurisdiccion||'Jurisdicción pendiente'}`;
  return <tr><td><strong>{row.nombre}</strong><p>DNI {row.dni}</p><small>{row.catedra_ids.length} cátedras inscriptas en el período</small></td>
    <td><span className={'academic-tag '+(row.plan_id?'academic-ok':'academic-pending')}>{row.plan_id?'Plan confirmado':'Plan pendiente de validar'}</span>
      {row.confirmacion_a_revisar&&<p>La confirmación anterior requiere revisión porque cambió la información vinculada.</p>}
      {puedeEditar?<><label className="block mt-2">Plan de {row.nombre}<select disabled={busy||!row.career_id} className="border rounded p-2 block w-full" value={plan} onChange={e=>setPlan(e.target.value)}>
        <option value="">Pendiente de validar</option>{plans.map(p=><option key={p.id} value={p.id}>{label(p)}</option>)}</select></label>
        {!row.career_id&&<p>Primero vinculá la carrera informada con la carrera del catálogo.</p>}
        <label className="block mt-2">Nota de validación<input maxLength={1000} disabled={busy} value={note} onChange={e=>setNote(e.target.value)} className="border rounded p-2 block w-full"/></label>
        <button disabled={busy} className="bg-blue-700 text-white rounded px-3 py-2 mt-2" onClick={save}>Guardar validación</button>
      </>:<p>{plans.find(p=>p.id===row.plan_id)?label(plans.find(p=>p.id===row.plan_id)):'No se asigna un plan por suposición.'}</p>}
      {error&&<p role="alert" className="text-red-700">{error}</p>}
    </td></tr>;
}

export default function EnrollmentPlans({cuatrimestre,puedeEditar=false}){
  const [index,setIndex]=useState(null),[selected,setSelected]=useState(''),[data,setData]=useState(null);
  const [career,setCareer]=useState(''),[query,setQuery]=useState(''),[search,setSearch]=useState('');
  const [pending,setPending]=useState(false),[offset,setOffset]=useState(0),[attempt,setAttempt]=useState(0);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const prefix='/api/inscripciones-planes/'+cuatrimestre;
  useEffect(()=>{let active=true;const c=new AbortController();setIndex(null);setError('');
    read(prefix,c.signal).then(d=>{if(active)setIndex(d);}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;c.abort();};
  },[prefix,attempt]);
  useEffect(()=>{let active=true;const c=new AbortController();setData(null);setError('');if(selected==='')return()=>c.abort();
    const params=new URLSearchParams({q:search,pendientes:String(pending),offset:String(offset)});
    read(prefix+'/cursos/'+selected+'?'+params,c.signal).then(d=>{if(active){setData(d);setCareer(d.course.career_id||'');}}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;c.abort();};
  },[prefix,selected,search,pending,offset,attempt]);
  const refresh=()=>setAttempt(a=>a+1);
  const saveCourse=async()=>{setBusy(true);setError('');try{
    await saveAcademic(prefix+'/cursos/'+selected,{revision:data.course.revision,catalog_revision:data.catalog_revision,
      source_token:data.course.source_token,career_id:career||null},'PUT');refresh();
  }catch(e){setError(e.message);}finally{setBusy(false);}};
  const currentCareer=index?.careers.find(c=>c.id===data?.course.career_id);
  return <div className="academic-catalog">
    <h2 className="text-2xl font-bold">Carreras y planes de los inscriptos</h2>
    <p className="my-3">La carrera informada en la carga se conserva. Si todavía no conocés el plan de un alumno, dejalo pendiente de validar: puede seguir formando parte de los conteos de su cátedra y período.</p>
    <p className="bg-blue-50 p-3 my-3">Conocer la carrera no confirma una versión del plan. Tampoco la deducimos a partir de sus materias. Las instituciones que cuenten con ese dato pueden confirmarlo aquí.</p>
    {!puedeEditar&&<p className="bg-amber-50 p-3 my-3">Modo consulta: podés revisar las inscripciones. Para confirmar carreras o planes, ingresá con la clave de edición.</p>}
    {error&&<p role="alert" className="text-red-700">{error} <button onClick={refresh}>Reintentar</button></p>}
    {!index&&!error&&<p role="status">Cargando carreras informadas…</p>}
    {index&&<>
      {!index.courses.length?<p className="academic-empty">No hay inscripciones cargadas en este cuatrimestre.</p>:<label className="block my-4">Carrera o curso informado<select aria-label="Carrera o curso informado" className="border rounded p-3 block w-full" value={selected} onChange={e=>{setSelected(e.target.value);setOffset(0);setQuery('');setSearch('');}}>
        <option value="">Elegí una carrera informada</option>{index.courses.map(c=><option key={c.curso_id} value={c.curso_id}>{c.carrera_informada} · {c.alumnos} alumnos · {c.planes_pendientes} planes pendientes</option>)}
      </select></label>}
      {selected!==''&&!data&&!error&&<p role="status">Cargando alumnos…</p>}
      {data&&<>
        <section className="border rounded p-4 my-4"><h3 className="font-bold">Carrera informada: {data.course.carrera_informada}</h3>
          <p>{data.course.alumnos} alumnos · {data.course.planes_confirmados} con plan confirmado · {data.course.planes_pendientes} con plan pendiente</p>
          <p>Carrera del catálogo: {currentCareer?.nombre||'Vínculo pendiente; se conserva el nombre importado'}</p>
          {puedeEditar&&data.course.curso_id!==0&&<><label className="block my-3">Vincular con carrera del catálogo<select aria-label="Vincular con carrera del catálogo" disabled={busy} className="border rounded p-2 block w-full" value={career} onChange={e=>setCareer(e.target.value)}><option value="">Dejar vínculo pendiente</option>{index.careers.map(c=><option key={c.id} value={c.id}>{c.nombre}</option>)}</select></label>
            <button disabled={busy||career===(data.course.career_id||'')} onClick={saveCourse} className="bg-slate-800 text-white px-3 py-2 rounded">Guardar vínculo de carrera</button>
            <p className="text-sm mt-2">Este vínculo se aplica a este curso y cuatrimestre. No asigna planes a sus alumnos. Si cambiás la carrera, sus confirmaciones de plan deberán revisarse.</p>
          </>}
          {data.course.curso_id===0&&<p>Estas inscripciones no traen curso o carrera de origen. Completá ese dato en la carga antes de asociarlas; no se agrupan como una sola carrera.</p>}
        </section>
        <form className="flex gap-3 items-end my-4" onSubmit={e=>{e.preventDefault();setOffset(0);setSearch(query);}}><label>Buscar alumno o DNI<input type="search" maxLength={100} className="border rounded p-2 block" value={query} onChange={e=>setQuery(e.target.value)}/></label><button className="border rounded p-2">Buscar</button>
          <label><input type="checkbox" checked={pending} onChange={e=>{setPending(e.target.checked);setOffset(0);}}/> Solo planes pendientes</label>
        </form>
        {puedeEditar&&<EditKey/>}
        <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Alumno de la carrera informada</th><th>Plan específico (opcional)</th></tr></thead><tbody>
          {data.rows.map(row=><StudentPlan key={`${row.alumno_id}:${row.revision}:${row.course_revision}:${data.catalog_revision}`} row={row} plans={currentCareer?.planes||[]} period={cuatrimestre} catalogRevision={data.catalog_revision} puedeEditar={puedeEditar} onSaved={refresh}/>)}
        </tbody></table></div>
        {!data.rows.length&&<p className="academic-empty">No hay alumnos que coincidan con los filtros.</p>}
        <div className="flex gap-4 items-center my-4"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Anterior</button><span>{data.total?offset+1:0}–{Math.min(offset+50,data.total)} de {data.total}</span><button disabled={offset+50>=data.total} onClick={()=>setOffset(offset+50)}>Siguiente</button></div>
      </>}
    </>}
  </div>;
}
