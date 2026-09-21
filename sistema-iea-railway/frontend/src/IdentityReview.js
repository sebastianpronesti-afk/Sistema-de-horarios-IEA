import React,{useEffect,useState} from 'react';
import {teacherLabel} from './identity';

export default function IdentityReview({kind,onTeacher}){
  const [data,setData]=useState(null),[error,setError]=useState('');
  useEffect(()=>{let active=true;const controller=new AbortController();
    fetch('/api/identidades/revision',{signal:controller.signal}).then(async response=>{
      if(!response.ok)throw Error('No se pudo revisar la identidad de los registros');
      return response.json();
    }).then(value=>{if(active)setData(value);}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;controller.abort();};
  },[]);
  if(error)return <p role="alert">{error}</p>;
  if(!data)return <p role="status">Revisando identidades…</p>;
  const groups=kind==='docentes'?[
    ['Documento repetido en fichas anteriores',data.documentos_repetidos||[]],
    ['Nombres coincidentes (pueden ser personas distintas)',data.nombres_coincidentes||[]],
    ['Documento pendiente o inválido',(data.docentes_sin_documento_valido||[]).map(id=>[id])],
  ]:[['Código repetido en registros anteriores',data.codigos_repetidos||[]]];
  const total=groups.reduce((sum,[,items])=>sum+items.length,0);
  return <details className="border rounded p-4 my-4"><summary>Revisión de identidades · {total} avisos</summary>
    <p className="my-3">{data.mensaje||'Revisá las coincidencias antes de modificar fichas. No se fusionan registros automáticamente.'}</p>
    {!total&&<p>No se encontraron coincidencias en los controles de identificación.</p>}
    {groups.map(([label,items])=>items.length>0&&<div key={label}><h3 className="font-bold my-2">{label}</h3><ul>{items.map((ids,i)=><li key={i}>{ids.map((id,index)=><React.Fragment key={id}>{index>0?' · ':''}{kind==='docentes'&&onTeacher?<button className="underline text-blue-700" onClick={()=>onTeacher(id)}>{teacherLabel(id)}</button>:kind==='docentes'?teacherLabel(id):`ID ${id}`}</React.Fragment>)}</li>)}</ul></div>)}
  </details>;
}
