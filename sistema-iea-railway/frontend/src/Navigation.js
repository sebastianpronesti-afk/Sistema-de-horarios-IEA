import React, {useState} from 'react';

const panel=(id,label,tabs)=>({id,label,tabs:tabs||[{id,label}]});
const tab=(id,label,keywords='')=>({id,label,keywords});
export const GENERAL_MENU=[
  {id:'inicio',label:'Inicio',items:[panel('dashboard','Panel general')]},
  {id:'planificacion',label:'Planificación',items:[
    panel('oferta','Oferta y materias',[tab('dictado','Oferta del cuatrimestre','cátedras que se dictan apertura'),tab('catedras','Materias y asignaciones','cátedras'),tab('decisiones','Decisiones de apertura','toma de decisiones'),tab('inscriptos_curso','Inscriptos del período','alumnos inscripciones por curso'),tab('inscripciones_planes','Carreras y planes de inscriptos','alumnos carrera informada plan opcional pendiente validar')]),
    panel('horarios','Horarios',[tab('calendario','Calendario'),tab('docentes_dia','Horarios por día','docentes día')]),
    panel('carreras','Horarios por carrera',[tab('plan_carrera','Horarios por carrera','plan molde sede'),tab('sugerencias','Sugerencias por carrera','sugerencia horarios armado')]),
    panel('carga_horaria','Carga horaria docente'),
    panel('validacion','Validación y cierre',[tab('chequeo','Revisión de cierre','listo publicar chequeo'),tab('solapamientos','Cruces de horarios','solapamientos docentes'),tab('solap_carreras','Cruces entre carreras','solapamientos carreras')]),
  ]},
  {id:'datos',label:'Personas y datos académicos',items:[
    panel('personal','Docentes',[tab('docentes','Fichas docentes'),tab('disponibilidad','Disponibilidad'),tab('necesitan_docente','Asignaciones pendientes','necesitan docente faltantes'),tab('nombres_docentes','Nombres y equivalencias','alias duplicados')]),
    panel('academicos','Carreras y planes de estudio',[tab('catedras_catalogo','Cátedras','catálogo códigos materias'),tab('planes_estudio','Planes de estudio','carreras resoluciones ministeriales jurisdicción catálogo materias correlatividades dobles titulaciones'),tab('cursos','Cursos de inscripción')]),
  ]},
  {id:'archivos',label:'Archivos y seguimiento',items:[panel('importar','Importar datos'),panel('exportar','Exportar'),panel('respaldos','Respaldos y recuperación',[tab('respaldos','Respaldos y recuperación','deshacer importación')]),panel('comparar','Comparar cuatrimestres')]},
];
export const IEA_MENU={id:'iea',label:'IEA',items:[
  {id:'terciarias',label:'Carreras terciarias',items:[
    panel('iea_planes_estudio','Planes de estudio',[tab('iea_planes_estudio','Planes de estudio','resoluciones jurisdicción catálogo materias dobles titulaciones')]),
    panel('iea_carreras','Horarios y sugerencias',[tab('iea_plan_carrera','Horarios por carrera','plan molde'),tab('iea_sugerencias','Sugerencias por carrera','sugerencia horarios armado')]),
    panel('edi_alumnos','EDI por cátedra'),panel('control_insc','Control de inscripciones'),
  ]},
  panel('bce','BCE y BEA',[tab('bce_bea','Materias BCE y BEA'),tab('iea_planes_secundario','Planes de estudio de secundario','catálogo módulos'),tab('iea_bce_import','Importar inscripciones BCE y BEA')]),panel('asincronicas','Materias asincrónicas'),
]};
export function menuFor(profile){return profile.id==='iea'?[...GENERAL_MENU,IEA_MENU]:GENERAL_MENU;}
export function flattenMenu(nodes,path=[]){return nodes.flatMap(node=>node.items?flattenMenu(node.items,[...path,node.label]):node.tabs.map(item=>({...item,panel:node,path:[...path,node.label]})));}
export function normalText(value){return value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();}
export function searchMenu(menu,query){const words=normalText(query).split(/\s+/).filter(Boolean);return flattenMenu(menu).filter(item=>words.every(word=>normalText([...item.path,item.label,item.keywords||''].join(' ')).includes(word)));}
export function currentItem(menu,id){return flattenMenu(menu).find(item=>item.id===id)||flattenMenu(menu)[0];}

export function Navigation({profile,activeView,onNavigate,footer,counts={}}){
  const [query,setQuery]=useState(''),[expanded,setExpanded]=useState({inicio:true,planificacion:true});
  const menu=menuFor(profile),results=searchMenu(menu,query);
  const navigate=id=>{
    const opened={};
    const reveal=nodes=>nodes.forEach(n=>{if(n.items){if(flattenMenu([n]).some(i=>i.id===id))opened[n.id]=true;reveal(n.items);}});
    reveal(menu);setExpanded(previous=>({...previous,...opened}));onNavigate(id);setQuery('');
  };
  const badge=id=>counts[id]>0?<span key={id} className="app-nav-badge">{counts[id]}</span>:null;
  const tree=(nodes,level=0)=>nodes.map(node=>{
    if(node.items){
      const contains=flattenMenu([node]).some(item=>item.id===activeView);
      const open=expanded[node.id]??contains;
      return <section key={node.id} className={`app-nav-group app-nav-level-${level}`}>
        <button type="button" className="app-nav-heading" aria-expanded={open} aria-controls={`nav-group-${node.id}`} onClick={()=>setExpanded({...expanded,[node.id]:!open})}>
          <span>{node.label}</span><span aria-hidden="true">{open?'−':'+'}</span>
        </button>
        <div id={`nav-group-${node.id}`} hidden={!open}>{tree(node.items,level+1)}</div>
      </section>;
    }
    const selected=node.tabs.some(t=>t.id===activeView);
    return <button key={node.id} type="button" className="app-nav-item" aria-current={selected?'page':undefined} onClick={()=>navigate(node.tabs[0].id)}>
      <span>{node.label}</span>{node.tabs.map(t=>badge(t.id))}
    </button>;
  });
  return <aside className="app-sidebar">
    <div className="app-brand"><h1>{profile.titulo}</h1><p>Planificación académica · v23.0</p></div>
    <label className="app-menu-search">Buscar en el menú
      <input type="search" value={query} placeholder="Ej.: docentes, horarios, EDI…" onChange={e=>setQuery(e.target.value)}
        onKeyDown={e=>{if(e.key==='Enter'&&query&&results[0]){e.preventDefault();navigate(results[0].id);}if(e.key==='Escape')setQuery('');}} />
    </label>
    <nav aria-label="Menú principal">
      {query.trim()?<div className="app-search-results"><p role="status">{results.length} resultados</p>
        {results.map(item=><button type="button" className="app-nav-item app-search-item" key={item.id} onClick={()=>navigate(item.id)}>
          <span>{item.label}<small>{item.path.join(' / ')}</small></span>{badge(item.id)}
        </button>)}{!results.length&&<p>Probá con otra función o sección.</p>}
      </div>:tree(menu)}
    </nav>
    <div className="app-sidebar-footer">{footer}</div>
  </aside>;
}

export function SectionTabs({item,onNavigate}){
  if(item.panel.tabs.length<2)return null;
  return <nav className="app-section-tabs" aria-label="Funciones de esta sección">
    {item.panel.tabs.map(t=><button type="button" key={t.id} aria-current={t.id===item.id?'page':undefined} onClick={()=>onNavigate(t.id)}>{t.label}</button>)}
  </nav>;
}

export function PeriodHeader({period,periods,onChange,item,readOnly,catalogMode=false}){
  return <header className="app-context-header">
    <div className="app-location"><p>{item.path.join(' / ')}</p><h2>{item.panel.label}</h2>{readOnly&&<span className="app-access">Acceso de consulta</span>}</div>
    {catalogMode?<div className="app-period-box"><strong>Información general</strong><p>Estos datos se conservan completos, independientemente del período de planificación.</p></div>:<div className="app-period-box"><label htmlFor="working-period">Cuatrimestre de trabajo</label>
      <select id="working-period" value={period} onChange={e=>onChange(e.target.value)} disabled={!periods.length}>
        {!periods.length&&<option value="">Sin cuatrimestres disponibles</option>}
        {periods.map(p=><option key={p.id} value={String(p.id)}>{p.nombre}</option>)}
      </select><p>Horarios, inscripciones y carga docente de este cuatrimestre.</p>
    </div>}
  </header>;
}
