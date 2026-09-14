import React,{useEffect,useMemo,useState} from 'react';
import {SubjectEditor,PlanEditor,EditKey,saveAcademic} from './AcademicEditors';

const situation={por_confirmar:'Situación por confirmar',vigente_informado:'Vigente según archivo',anterior:'Plan anterior',no_ofertado:'No ofertado según archivo',futuro:'Inicio futuro informado'};
const modality={presencial:'Presencial',distancia:'A distancia'};
const matching={confirmado:'Asociación confirmada',coincide:'Coincide con el catálogo',revisar_asociacion:'Revisar asociación',revisar_codigo:'Revisar código',sin_vinculo:'Sin vínculo confirmado',espacio_edi:'Espacio EDI'};
const normalized=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const origin=value=>value?`${value.hoja} · fila ${value.fila}`:'';
const pending=s=>!['coincide','confirmado','espacio_edi'].includes(s.vinculo?.estado)||(s.catedra_id===undefined&&s.observaciones?.length>0)||s.anio==null||s.cuatrimestre==null;

async function request(path,signal){
  const response=await fetch(path,{signal});
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'No se pudo cargar el catálogo');
  return data;
}

function Subjects({rows=[],onEdit}){
  const [query,setQuery]=useState(''),[onlyPending,setOnlyPending]=useState(false);
  const visible=useMemo(()=>rows.filter(s=>(!onlyPending||pending(s))&&normalized([s.nombre,s.codigo_archivo,s.vinculo?.catedra?.codigo].join(' ')).includes(normalized(query)))
    .sort((a,b)=>(a.anio??99)-(b.anio??99)||(a.cuatrimestre??99)-(b.cuatrimestre??99)||a.nombre.localeCompare(b.nombre)),[rows,query,onlyPending]);
  return <section>
    <div className="academic-subject-controls"><label>Buscar materia<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Nombre o código"/></label>
      <label className="academic-check"><input type="checkbox" checked={onlyPending} onChange={e=>setOnlyPending(e.target.checked)}/>Solo pendientes de revisión</label>
      <span role="status">{visible.length} de {rows.length} materias</span></div>
    <div className="academic-table-wrap"><table className="academic-table"><caption>Materias del plan y correspondencia con las cátedras existentes</caption>
      <thead><tr><th scope="col">Año académico</th><th scope="col">Cuatrimestre académico</th><th scope="col">Materia del plan</th><th scope="col">Código y cátedra del sistema</th><th scope="col">Correlatividades y revisión</th></tr></thead>
      <tbody>{visible.map(s=><tr key={s.id}>
        <td>{s.anio?`${s.anio}° año`:'Año pendiente'}</td><td>{s.cuatrimestre?`${s.cuatrimestre}° cuatrimestre`:'Cuatrimestre pendiente'}</td>
        <td><strong>{s.nombre}</strong>{s.plan_origen&&<small>{s.plan_origen}</small>}{onEdit&&<button className="block text-blue-700 underline mt-2" onClick={()=>onEdit(s)}>Editar materia</button>}</td>
        <td><span className={`academic-tag ${['coincide','confirmado'].includes(s.vinculo?.estado)?'academic-ok':'academic-pending'}`}>{matching[s.vinculo?.estado]||'Por revisar'}</span>
          {onEdit&&<button className="block text-blue-700 underline my-2" onClick={()=>onEdit(s)}>{s.vinculo?.catedra?'Cambiar cátedra':'Asociar cátedra'}</button>}
          {s.vinculo?.catedra?<p><strong>{s.vinculo.catedra.codigo}</strong> · {s.vinculo.catedra.nombre}</p>:<>
            <p>Referencia en archivo: <strong>{s.codigo_archivo||'Sin código'}</strong></p>
            {s.vinculo?.candidatas?.map(c=><small key={c.id}>Cátedra a revisar: {c.codigo} · {c.nombre}</small>)}</>}
        </td>
        <td><p>{Array.isArray(s.correlativa_ids)?s.correlativa_ids.map(id=>rows.find(r=>r.id===id)?.nombre||'Materia pendiente').join(', ')||'Sin correlatividades':s.correlatividades||'No informadas'}</p>{s.revision_nota&&<p>{s.revision_nota}</p>}<details><summary>Antecedentes de importación</summary><p>{origin(s.origen)}</p>{s.observaciones?.length>0&&<ul>{s.observaciones.map((v,i)=><li key={i}>{v}</li>)}</ul>}</details>
          {(s.anio_sistema_archivo||s.cuatrimestre_sistema_archivo)&&<details><summary>Comparar con el sistema anterior</summary>
            <p>Año registrado en el archivo: {s.anio_sistema_archivo||'Sin dato'}<br/>Cuatrimestre registrado: {s.cuatrimestre_sistema_archivo||'Sin dato'}</p>
            <p>Estos valores se conservan para revisión. Se utiliza la ubicación académica del plan.</p></details>}
        </td>
      </tr>)}</tbody></table>{!visible.length&&<p className="academic-empty">No hay materias que coincidan con estos filtros.</p>}</div>
  </section>;
}

export default function AcademicPlans({initialLevel='',puedeEditar=false}){
  const [editing,setEditing]=useState(null),[actionError,setActionError]=useState('');
  const [catalog,setCatalog]=useState(null),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  const [query,setQuery]=useState(''),[level,setLevel]=useState(initialLevel),[jurisdiction,setJurisdiction]=useState(''),[mode,setMode]=useState(''),[status,setStatus]=useState('');
  const [section,setSection]=useState('careers'),[selection,setSelection]=useState(null),[detail,setDetail]=useState(null),[detailError,setDetailError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();let active=true;setCatalog(null);setError('');
    request('/api/planes-estudio',controller.signal).then(data=>{
      if(!Array.isArray(data?.careers)||!Array.isArray(data?.articulations))throw new Error('El catálogo recibido está incompleto');
      if(active)setCatalog(data);
    }).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;controller.abort();};
  },[attempt]);
  useEffect(()=>{
    setDetail(null);setDetailError('');if(!selection)return;
    const controller=new AbortController();let active=true;
    const path=selection.type==='articulation'?`/api/planes-estudio/articulaciones/${selection.id}`:selection.type==='pending'?`/api/planes-estudio/carreras/${selection.id}/pendientes`:`/api/planes-estudio/${selection.id}`;
    request(path,controller.signal).then(data=>{
      if(selection.type==='articulation'?!Array.isArray(data?.bloques):!Array.isArray(data?.materias))throw new Error('El detalle recibido está incompleto');
      if(active)setDetail(data);
    }).catch(e=>{if(active)setDetailError(e.message);});
    return()=>{active=false;controller.abort();};
  },[selection,attempt]);
  const careers=catalog?.careers||[];
  const saved=()=>{setEditing(null);setAttempt(a=>a+1);};
  const createPlan=async(career)=>{setActionError('');try{await saveAcademic('/api/planes-estudio/editar',{operation:'new_plan',career_id:career.id,revision:catalog.revision});saved();}catch(e){setActionError(e.message);}};
  const allPlans=careers.flatMap(c=>c.planes);
  const jurisdictions=[...new Set(allPlans.map(p=>p.jurisdiccion).filter(Boolean))].sort();
  const visible=careers.filter(c=>!level||c.nivel===level).map(c=>({...c,planes:c.planes.filter(p=>
    (!jurisdiction||p.jurisdiccion===jurisdiction)&&(!mode||p.modalidad===mode)&&(!status||p.situacion===status)&&
    normalized([c.nombre,p.nombre_oficial,p.resolucion,p.etiqueta].join(' ')).includes(normalized(query)))}))
    .filter(c=>c.planes.length||(!jurisdiction&&!mode&&!status&&normalized(c.nombre).includes(normalized(query))));
  const articulations=(catalog?.articulations||[]).filter(a=>normalized(a.nombre).includes(normalized(query)));
  const open=(type,id)=>{setDetail(null);setDetailError('');setSelection({type,id});setEditing(null);};
  if(error)return <div className="academic-catalog" role="alert"><p>{error}</p><button onClick={()=>setAttempt(a=>a+1)}>Reintentar catálogo</button></div>;
  if(!catalog)return <div className="academic-catalog" role="status">Cargando carreras y planes de estudio…</div>;
  return <div className="academic-catalog">
    <header className="academic-intro"><p className="academic-eyebrow">Catálogo académico</p><h2>Carreras y planes de estudio</h2>
      <p>Cada resolución conserva su plan y sus materias. El catálogo es independiente del cuatrimestre de trabajo.</p>
      <p>Completá cada plan y confirmá sus cátedras. En Planificación elegís qué materias ofrecer en cada período.</p>
      {!puedeEditar&&<p className="bg-amber-50 p-3">Estás en modo consulta. Para asociar cátedras o corregir materias, cerrá sesión e ingresá con la clave de edición.</p>}
      {catalog.source&&<details><summary>Antecedentes del catálogo</summary><small>Fuente: {catalog.source.filename} · revisión {catalog.source.revision}</small></details>}</header>
    {actionError&&<p role="alert">{actionError}</p>}
    {selection?<>
      <button className="academic-back" onClick={()=>{setSelection(null);setDetail(null);}}>Volver al catálogo</button>
      {detailError?<div role="alert"><p>{detailError}</p><button onClick={()=>setSelection({...selection})}>Reintentar detalle</button></div>:!detail?<p role="status">Cargando detalle…</p>:<>
        <section className="academic-detail-head"><h3>{detail.carrera||detail.nombre}</h3>
          {selection.type==='plan'&&<><h4>{detail.nombre_oficial||'Nombre oficial pendiente'}</h4>
            <dl><div><dt>Plan y resolución</dt><dd>{detail.etiqueta} · {detail.resolucion||'Resolución pendiente'}</dd></div>
              <div><dt>Modalidad</dt><dd>{modality[detail.modalidad]||'Por confirmar'}</dd></div>
              <div><dt>Jurisdicción aprobante</dt><dd>{detail.jurisdiccion||'Por confirmar'}</dd></div>
              <div><dt>Título</dt><dd>{detail.titulo||'Por completar'}</dd></div>
              <div><dt>Situación informada</dt><dd>{situation[detail.situacion]||'Por confirmar'}</dd></div>
              <div><dt>Inicio informado</dt><dd>{detail.inicio_informado||'Sin fecha informada'}</dd></div></dl>
            {detail.nota_vigencia&&<p>Nota del archivo: {detail.nota_vigencia}</p>}
            {puedeEditar&&<div className="flex gap-3 my-3"><button className="text-blue-700 underline" onClick={()=>setEditing('plan')}>Editar información del plan</button><button className="text-blue-700 underline" onClick={()=>setEditing({})}>Agregar materia</button></div>}
            <p>{detail.resumen.materias} materias · {detail.resumen.vinculadas} coincidencias con el catálogo de cátedras · {detail.resumen.por_revisar} asociaciones por revisar</p>
          </>}
          {detail.observaciones?.length>0&&<ul className="academic-notes">{detail.observaciones.map((n,i)=><li key={i}>{n}</li>)}</ul>}
        </section>
        {editing==='plan'&&<PlanEditor plan={detail} revision={detail.revision} onSaved={saved} onClose={()=>setEditing(null)}/>}
        {editing&&typeof editing==='object'&&<SubjectEditor subject={editing} plan={selection.type==='plan'?detail:null} career={selection.type==='pending'?careers.find(c=>c.id===selection.id):null} revision={detail.revision} onSaved={saved} onClose={()=>setEditing(null)}/>}
        <p className="academic-explanation">Los códigos y nombres de las cátedras existentes se conservan. Una referencia del archivo que no coincide queda pendiente de asociación.</p>
        {selection.type==='articulation'?<>
          <p>Estas hojas describen posibles dobles titulaciones. Las equivalencias y los planes participantes requieren revisión antes de usarse para organizar una cursada.</p>
          {!detail.bloques.length&&<p className="academic-empty">El archivo enumera esta combinación, pero no incluye el detalle de sus materias.</p>}
          {detail.bloques.map((block,i)=><section key={i}><h4>{block.nombre}</h4><Subjects rows={block.materias}/></section>)}
        </>:<>
          {detail.modulos?.length>0&&<details className="academic-modules"><summary>Módulos de estudio ({detail.modulos.length})</summary>
            <ul>{detail.modulos.map((m,i)=><li key={i}>{m.nombre} · {m.cuatrimestre?`${m.cuatrimestre}° cuatrimestre`:'Cuatrimestre pendiente'}{m.codigo_archivo&&` · referencia ${m.codigo_archivo}`}</li>)}</ul></details>}
          <Subjects key={selection.id} rows={detail.materias} onEdit={puedeEditar?setEditing:undefined}/>
        </>}
      </>}
    </>:<>
      <div className="academic-summary"><span><strong>{careers.length}</strong> carreras y programas</span><span><strong>{allPlans.length}</strong> planes y propuestas</span><span><strong>{catalog.articulations.length}</strong> registros de dobles titulaciones para revisar</span></div>
      <nav className="academic-switch" aria-label="Contenido del catálogo"><button aria-pressed={section==='careers'} onClick={()=>{setSection('careers');setQuery('');}}>Carreras y planes</button><button aria-pressed={section==='articulations'} onClick={()=>{setSection('articulations');setQuery('');}}>Dobles titulaciones</button></nav>
      <div className="academic-filters"><label>Buscar carrera o resolución<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ej.: Administración, 261/03…"/></label>
        {section==='careers'&&<><label>Nivel<select value={level} onChange={e=>setLevel(e.target.value)}><option value="">Cualquier nivel</option><option value="terciario">Terciario</option><option value="secundario">Secundario</option></select></label>
          <label>Modalidad<select value={mode} onChange={e=>setMode(e.target.value)}><option value="">Cualquier modalidad</option>{Object.entries(modality).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
          <label>Jurisdicción<select value={jurisdiction} onChange={e=>setJurisdiction(e.target.value)}><option value="">Cualquier jurisdicción</option>{jurisdictions.map(j=><option key={j}>{j}</option>)}</select></label>
          <label>Situación informada<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">Cualquier situación</option>{Object.entries(situation).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label></>}
      </div>
      {!careers.length&&!catalog.articulations.length&&<p className="academic-empty">Esta institución todavía no tiene un catálogo de planes de estudio configurado.</p>}
      {section==='careers'?<>
        <p role="status">{visible.length} carreras y programas encontrados</p>{puedeEditar&&<EditKey/>}
        {visible.map(c=><section key={c.id} className="academic-career"><h3>{c.nombre}<small>{c.nivel==='secundario'?'Secundario':'Terciario'} · {c.planes.length} planes</small></h3>
          {puedeEditar&&<button className="text-blue-700 underline my-2" onClick={()=>createPlan(c)}>Agregar plan</button>}{!c.planes.length&&<p>El archivo incluye esta carrera, pero su plan está pendiente de completar.</p>}
          <div className="academic-plan-grid">{c.planes.map(p=><button key={p.id} className="academic-plan-card" onClick={()=>open('plan',p.id)}>
            <span className="academic-plan-mode">{modality[p.modalidad]||'Modalidad por confirmar'}</span><strong>{p.etiqueta} · {p.resolucion||'Resolución pendiente'}</strong>
            <span>{p.jurisdiccion||'Jurisdicción por confirmar'}</span><span>{p.nombre_oficial||'Nombre oficial pendiente'}</span>
            <span className="academic-tag">{situation[p.situacion]||'Por confirmar'}</span><small>{p.resumen.materias} materias · {p.resumen.por_revisar} asociaciones por revisar</small>
          </button>)}</div>
          {c.materias_sin_plan>0&&<button className="academic-pending-link" onClick={()=>open('pending',c.id)}>Revisar {c.materias_sin_plan} materias sin plan identificado</button>}
        </section>)}
      </>:<div className="academic-plan-grid">{articulations.map(a=><button key={a.id} className="academic-plan-card" onClick={()=>open('articulation',a.id)}><strong>{a.nombre}</strong><span>{a.materias} materias en las comparaciones</span><span className="academic-tag academic-pending">Planes y equivalencias por confirmar</span></button>)}</div>}
    </>}
  </div>;
}
