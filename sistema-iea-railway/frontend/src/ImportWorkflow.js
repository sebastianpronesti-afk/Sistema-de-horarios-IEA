import React, {useCallback, useEffect, useState} from 'react';

const TYPES = {horarios:'Horarios y designaciones', inscripciones:'Alumnos e inscripciones', plan:'Plan de carrera'};
const TABLES = {asignaciones:'Horario',inscripciones:'Inscripción',plan_carrera:'Plan',alumnos:'Alumno',docentes:'Docente',catedras:'Materia',catedra_dictado:'Oferta del período'};
const FIELDS = {asignacion_id:'ID de asignación',codigo_materia:'Código de materia',materia:'Nombre de materia',carrera:'Carrera',sede:'Sede',periodo_id:'ID de período',comision:'Comisión',turno:'Turno',dia:'Día',hora_inicio:'Hora de inicio',hora_fin:'Hora de fin',docente_id:'ID docente',docente:'Nombre docente',docente_dni:'DNI docente',modalidad:'Modalidad',link_meet:'Enlace de clase',recibe_alumnos_presenciales:'Recibe alumnos presenciales',dni:'DNI alumno',alumno:'Nombre completo alumno',nombre:'Nombre',apellido:'Apellido',email:'Correo',es_edi:'Inscripción EDI',edi_materia:'Materia EDI',anno:'Año de carrera',dia_tm:'Día mañana',hora_tm:'Hora mañana',dia_tn:'Día noche',hora_tn:'Hora noche',cuatrimestre_id:'Período',sede_id:'Sede (ID)',catedra_id:'Materia (ID)',alumno_id:'Alumno (ID)',codigo:'Código',codigo_catedra:'Código de materia',nombre_catedra:'Nombre de materia',se_dicta:'Se dicta',curso_nombre:'Carrera',sede_referencia:'Sede',modalidad_alumno:'Modalidad del alumno',modificada:'Edición manual'};
const INPUTS = {
  horarios:['asignacion_id','codigo_materia','materia','sede','comision','carrera','turno','dia','hora_inicio','hora_fin','docente_id','docente','docente_dni','modalidad','link_meet','recibe_alumnos_presenciales','periodo_id'],
  inscripciones:['codigo_materia','dni','nombre','apellido','alumno','email','carrera','sede','turno','modalidad','es_edi','edi_materia','periodo_id'],
  plan:['codigo_materia','materia','carrera','sede','anno','dia_tm','hora_tm','dia_tn','hora_tn'],
};

async function request(url, options={}) {
  const response=await fetch(url,options);
  const data=await response.json();
  if (!response.ok) {
    const detail=data.detail;
    throw new Error(typeof detail==='string' ? detail : detail?.mensaje || 'No se pudo completar la operación. Volvé a revisar los datos.');
  }
  return data;
}

function shown(value) {
  if (value===null || value===undefined || value==='') return '—';
  if (typeof value==='boolean') return value ? 'Sí' : 'No';
  return String(value);
}

export function ChangesTable({changes=[]}) {
  const [page,setPage]=useState(0);
  useEffect(() => setPage(0),[changes]);
  const pages=Math.max(1,Math.ceil(changes.length/25));
  return <div>
    <div className="overflow-x-auto border rounded-lg">
      <table className="w-full text-xs text-left"><thead className="bg-slate-100"><tr>
        <th className="p-2">Acción</th><th className="p-2">Registro</th><th className="p-2">Cambios</th>
      </tr></thead><tbody>{changes.slice(page*25,page*25+25).map((change,index) => {
        const before=change.antes,after=change.despues;
        const keys=[...new Set([...Object.keys(before||{}),...Object.keys(after||{})])]
          .filter(key => key!=='id' && JSON.stringify(before?.[key])!==JSON.stringify(after?.[key]));
        return <tr key={index} className="border-t align-top">
          <td className="p-2 font-medium">{!before?'Agregar':!after?'Eliminar':'Modificar'}</td>
          <td className="p-2">{TABLES[change.tabla]||change.tabla} · {change.origen?.codigo_materia || (change.id>0?`#${change.id}`:'Nuevo')}
            {change.origen? <div className="text-slate-500">{change.origen._hoja}, fila {change.origen._fila}</div>:null}</td>
          <td className="p-2"><details><summary className="cursor-pointer">Ver {keys.length} campos</summary>
            <dl className="mt-2 space-y-1">{keys.map(key => <div key={key}>
              <dt className="font-medium inline">{FIELDS[key]||key}: </dt>
              <dd className="inline break-words">{shown(before?.[key])} → {shown(after?.[key])}</dd>
            </div>)}</dl>
          </details></td>
        </tr>;
      })}</tbody></table>
    </div>
    <div className="flex items-center gap-3 text-xs my-2">
      <button type="button" disabled={page===0} onClick={() => setPage(page-1)} className="px-2 py-1 border rounded disabled:opacity-40">Anterior</button>
      <span>Página {page+1} de {pages} · {changes.length} cambios</span>
      <button type="button" disabled={page+1>=pages} onClick={() => setPage(page+1)} className="px-2 py-1 border rounded disabled:opacity-40">Siguiente</button>
    </div>
  </div>;
}

export function ImportHistory({period,canEdit=true,refresh=0,onChange}) {
  const [items,setItems]=useState([]),[preview,setPreview]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const load=useCallback(async () => {
    try {const data=await request('/api/importaciones/historial'+(period && period!=='todos'?`?cuatrimestre_id=${period}`:''));setItems(data.historial||[]);}
    catch(e){setError(e.message);}
  },[period]);
  useEffect(() => {setPreview(null);load();},[load,refresh]);
  const inspect=async id => {
    setBusy(true);setError('');setNotice('');setPreview(null);
    try {setPreview(await request(`/api/importaciones/historial/${id}/vista-previa`,{method:'POST'}));}
    catch(e){setError(e.message);} finally {setBusy(false);}
  };
  const restore=async () => {
    setBusy(true);setError('');
    try {
      const result=await request(`/api/importaciones/historial/${preview.historial_id}/restaurar`,
        {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:preview.token})});
      setNotice(result.mensaje);setPreview(null);await load();if(onChange)await onChange();
    } catch(e){setError(e.message);setPreview(null);} finally {setBusy(false);}
  };
  return <section className="bg-white border rounded-xl p-5 my-6" aria-label="Historial de importaciones">
    <h3 className="text-lg font-bold">Importaciones y recuperación</h3>
    <p className="text-sm text-slate-500 my-2">Cada operación conserva el estado de todos los registros que modificó. La recuperación se detiene si encuentra cambios posteriores incompatibles.</p>
    {error&&<p role="alert" className="p-3 bg-red-50 text-red-700 my-3">{error}</p>}
    {notice&&<p role="status" className="p-3 bg-emerald-50 text-emerald-800 my-3">{notice}</p>}
    {!items.length&&<p className="text-sm text-slate-500">Todavía no hay operaciones del nuevo circuito.</p>}
    <div className="max-h-72 overflow-auto">{items.map(item => <div key={item.id} className="flex justify-between items-center gap-3 py-3 border-b text-sm">
      <div><b>#{item.id} · {TYPES[item.tipo]||'Recuperación'}</b><p>{item.archivo}</p>
        <p className="text-xs text-slate-500">{String(item.creado_en||'').replace('T',' ').slice(0,19)} · {item.cuatrimestre_id?`Período #${item.cuatrimestre_id}`:'Molde compartido'} · {item.sede_id?`Sede #${item.sede_id}`:'Todas las sedes'}</p></div>
      {item.restaurada_en?<span className="text-emerald-700 text-xs">Recuperada</span>:<button type="button" onClick={() => inspect(item.id)} disabled={busy||!canEdit} className="px-3 py-2 border rounded-lg disabled:opacity-40">Revisar recuperación</button>}
    </div>)}</div>
    {preview&&<div className="mt-4 border-t pt-4">
      <h4 className="font-bold mb-2">Cambios para recuperar el estado previo a #{preview.historial_id}</h4>
      {preview.conflictos?.length>0&&<div role="alert" className="p-3 bg-amber-50 text-amber-900 mb-3"><p>No se puede recuperar automáticamente:</p><ul>{preview.conflictos.map((c,i)=><li key={i}>{c}</li>)}</ul></div>}
      <ChangesTable changes={preview.cambios}/>
      <div className="flex gap-3 mt-3"><button type="button" disabled={busy||!canEdit||!preview.puede_restaurar} onClick={restore} className="bg-blue-700 text-white rounded-lg px-4 py-2 disabled:opacity-40">{busy?'Recuperando…':'Confirmar recuperación'}</button>
        <button type="button" disabled={busy} onClick={()=>setPreview(null)} className="px-4 py-2 border rounded-lg">Cancelar</button></div>
    </div>}
  </section>;
}

export default function ImportWorkflow({periods=[],campuses=[],initialPeriod,canEdit=true,onApplied}) {
  const [kind,setKind]=useState('horarios'),[period,setPeriod]=useState(initialPeriod&&initialPeriod!=='todos'?String(initialPeriod):'');
  const [campus,setCampus]=useState(''),[mode,setMode]=useState('actualizar'),[format,setFormat]=useState('auto');
  const [file,setFile]=useState(null),[mapping,setMapping]=useState({}),[preview,setPreview]=useState(null),[columns,setColumns]=useState([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState(null),[ack,setAck]=useState(false),[refresh,setRefresh]=useState(0);
  useEffect(()=>{setPreview(null);setAck(false);setResult(null);setError('');},[kind,period,campus,mode,format,file,mapping]);
  const params=()=>{
    const query=new URLSearchParams({tipo:kind,sede_id:campus,modo:mode,formato:format});
    if(kind!=='plan')query.set('cuatrimestre_id',period);
    return query.toString();
  };
  const send=async applying => {
    setBusy(true);setError('');setResult(null);
    try {
      const form=new FormData();form.append('file',file);form.append('mapeo',JSON.stringify(mapping));
      if(applying)form.append('token',preview.token);
      const data=await request('/api/importaciones/'+(applying?'aplicar':'vista-previa')+'?'+params(),{method:'POST',body:form});
      if(applying){setResult(data);setPreview(null);setRefresh(x=>x+1);if(onApplied)await onApplied();}
      else{setPreview(data);setColumns(data.columnas||[]);setAck(false);}
    } catch(e){setError(e.message);setPreview(null);} finally{setBusy(false);}
  };
  return <section aria-label="Importación con vista previa">
    <div className="bg-white rounded-xl border border-blue-200 p-5 mb-5">
      <h3 className="text-xl font-bold">Cargar, revisar y confirmar</h3>
      <p className="text-sm text-slate-600 my-2">Subí la planilla, revisá las diferencias y confirmá los cambios. Podés usar las planillas del IEA, la plantilla común o un archivo con columnas equivalentes.</p>
      <fieldset disabled={busy} className="grid md:grid-cols-3 gap-4 my-4">
        <label className="text-sm">Datos a importar<select aria-label="Datos a importar" value={kind} onChange={e=>{setKind(e.target.value);setMapping({});setColumns([]);}} className="block w-full border rounded p-2 mt-1">{Object.entries(TYPES).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
        <label className="text-sm">Período<select aria-label="Período de importación" disabled={kind==='plan'} value={period} onChange={e=>setPeriod(e.target.value)} className="block w-full border rounded p-2 mt-1"><option value="">Elegí un período</option>{periods.map(p=><option key={p.id} value={p.id}>{p.nombre}</option>)}</select>{kind==='plan'&&<span className="text-xs text-amber-800">Molde compartido entre períodos.</span>}</label>
        <label className="text-sm">Sede<select aria-label="Sede de importación" value={campus} onChange={e=>setCampus(e.target.value)} className="block w-full border rounded p-2 mt-1"><option value="">Elegí el alcance</option><option value="0">Todas las sedes</option>{campuses.map(s=><option key={s.id} value={s.id}>{s.nombre}</option>)}</select></label>
        <label className="text-sm">Modo<select aria-label="Modo de importación" value={mode} onChange={e=>setMode(e.target.value)} className="block w-full border rounded p-2 mt-1"><option value="actualizar">Actualizar y conservar ausentes</option><option value="reemplazar">Reemplazar dentro del alcance</option></select></label>
        <label className="text-sm">Formato<select aria-label="Formato del archivo" value={format} onChange={e=>setFormat(e.target.value)} className="block w-full border rounded p-2 mt-1"><option value="auto">Detectar automáticamente</option><option value="estandar">Tabla con encabezados</option><option value="iea">Planilla del IEA</option></select></label>
        <label className="text-sm">Archivo XLSX o CSV<input aria-label="Archivo a importar" type="file" accept=".xlsx,.csv" onChange={e=>{setFile(e.target.files?.[0]||null);setMapping({});setColumns([]);}} className="block w-full mt-2"/></label>
      </fieldset>
      <p className="text-sm p-3 bg-slate-50 rounded mb-3">{mode==='actualizar'?'Se conservarán los registros que no aparezcan en el archivo.':'Se propondrán bajas para los registros ausentes únicamente dentro del alcance elegido.'} {kind==='inscripciones'?'Las bajas afectan inscripciones; se conservan las personas.':''}</p>
      <div className="flex flex-wrap gap-3 items-center">
        <a href={`/api/importaciones/plantilla?tipo=${kind}`} className="text-blue-700 underline text-sm">Descargar plantilla común</a>
        <button type="button" disabled={busy||!canEdit||!file||campus===''||(kind!=='plan'&&!period)} onClick={()=>send(false)} className="px-4 py-2 bg-blue-700 text-white rounded-lg disabled:opacity-40">{busy?'Procesando…':'Analizar y ver diferencias'}</button>
      </div>
      {error&&<p role="alert" className="p-3 my-3 bg-red-50 text-red-700">{error}</p>}
      {result&&<p role="status" className="p-3 my-3 bg-emerald-50 text-emerald-900">{result.sin_cambios?'El archivo coincide con los datos actuales. No hubo cambios.':`Importación aplicada. Podés recuperar el estado anterior desde la operación #${result.historial_id}.`}</p>}
        {columns?.length>0&&<details className="my-3"><summary className="cursor-pointer text-sm text-blue-700">Relacionar columnas de mi archivo</summary><div className="grid md:grid-cols-3 gap-3 mt-3">{INPUTS[kind].map(field=><label key={field} className="text-xs">{FIELDS[field]}<select value={mapping[field]||''} disabled={busy} onChange={e=>setMapping({...mapping,[field]:e.target.value})} className="block w-full border rounded p-2"><option value="">Detección automática</option>{columns.map(name=><option key={name} value={name}>{name}</option>)}</select></label>)}</div><p className="text-xs mt-2">Después de cambiar una columna, volvé a analizar el archivo.</p></details>}
      {preview&&<div className="mt-5 border-t pt-4">
        <h4 className="font-bold">Vista previa · {preview.archivo}</h4>
        <p className="text-sm my-2">{preview.alcance.sede} · {kind==='plan'?'Molde compartido':periods.find(p=>String(p.id)===period)?.nombre} · {mode==='actualizar'?'Actualizar':'Reemplazar'}</p>
        <div className="grid grid-cols-4 gap-2 my-3">{[['altas','Altas'],['modificaciones','Modificaciones'],['bajas','Bajas'],['sin_cambios','Sin cambios']].map(([key,label])=><div key={key} className="bg-slate-50 p-3 rounded text-center"><b className="text-xl">{preview.resumen[key]}</b><p className="text-xs">{label}</p></div>)}</div>
        {preview.resumen.cambios_relacionados>0&&<p className="text-sm p-3 bg-amber-50 text-amber-900 my-3">También se proponen {preview.resumen.cambios_relacionados} cambios en datos relacionados, como docentes, alumnos, enlaces u oferta. Los datos personales y enlaces son compartidos; revisalos en el detalle.</p>}
        {preview.errores.length>0&&<div role="alert" className="p-3 bg-red-50 text-red-800 my-3"><p className="font-bold">Corregí estos errores antes de aplicar:</p><ul className="list-disc pl-5 max-h-64 overflow-auto">{preview.errores.map((e,i)=><li key={i}>{e.hoja} · fila {e.fila}: {e.mensaje}</li>)}</ul></div>}
        {preview.advertencias.length>0&&<ul className="bg-amber-50 p-3 my-3 text-sm">{preview.advertencias.map((w,i)=><li key={i}>{w}</li>)}</ul>}

        <ChangesTable changes={preview.cambios}/>
        {preview.resumen.bajas>0&&<label className="flex gap-2 text-sm my-3"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={busy}/><span>Revisé las {preview.resumen.bajas} bajas propuestas dentro del alcance elegido.</span></label>}
        <button type="button" disabled={busy||!canEdit||!preview.puede_aplicar||(preview.resumen.bajas>0&&!ack)} onClick={()=>send(true)} className="mt-3 px-4 py-2 bg-emerald-700 text-white rounded-lg disabled:opacity-40">Confirmar y aplicar cambios</button>
      </div>}
    </div>
    <ImportHistory period={period} canEdit={canEdit} refresh={refresh} onChange={onApplied}/>
  </section>;
}
