const {test,afterEach}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const {JSDOM}=require('jsdom'),{buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const key of ['window','document','HTMLElement','Event','MouseEvent','localStorage','FormData'])global[key]=dom.window[key];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react'),{act,Simulate}=require('react-dom/test-utils'),{createRoot}=require('react-dom/client');
function compile(file){const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src',file)],bundle:true,loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});const mod=new Module(path.join(__dirname,file+'.cjs'),module);mod.filename=path.join(__dirname,file+'.cjs');mod.paths=module.paths;mod._compile(built.outputFiles[0].text,mod.filename);return mod.exports;}
const App=compile('App.js').default,{choosePeriod}=compile('periods.js');
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures.json')));
const iea=JSON.parse(fs.readFileSync(path.join(__dirname,'../backend/app/profiles/iea.json')));
const other=JSON.parse(fs.readFileSync(path.join(__dirname,'../backend/app/profiles/institucion-ejemplo.json')));
const scoped=['/api/catedras','/api/docentes','/api/horarios/solapamientos','/api/catedras/necesitan-docente','/api/solapamientos-carreras','/api/dashboard','/api/plan-carrera/sugerencias','/api/sugerencias-armado'];
let root,calls,handler,profile;
const settle=async()=>{for(let i=0;i<3;i++)await act(async()=>new Promise(resolve=>setTimeout(resolve,5)));};
const button=(text,scope=document)=>[...scope.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
async function click(b){assert.ok(b,'Button exists');await act(async()=>b.click());await settle();}
async function select(id,value){await act(async()=>{const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));});await settle();}
async function search(text){await act(async()=>Simulate.change(document.querySelector('input[type="search"]'),{target:{value:text}}));await settle();}
async function mount(selected=iea,overrides={}){
  profile=selected;calls=[];handler=null;localStorage.clear();localStorage.setItem('iea_auth','true');localStorage.setItem('iea_rol','editor');
  if(overrides.saved)localStorage.setItem('horarios.periodo.'+profile.id,overrides.saved);
  global.fetch=async url=>{
    const parsed=new URL(url,'https://validation.invalid');calls.push(parsed);
    if(handler){const result=handler(parsed);if(result)return await result;}
    const data=parsed.pathname==='/api/institucion'?profile:overrides[parsed.pathname]??fixtures[parsed.pathname]??{};
    return {ok:true,json:async()=>structuredClone(data)};
  };
  root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(App)));await settle();
}

const academicCatalog={revision:0,source:null,articulations:[],careers:[{id:'career',nombre:'Carrera de prueba',nivel:'terciario',materias_sin_plan:0,planes:[{id:'p1',etiqueta:'Plan 1',resolucion:'RES-TEST',resumen:{materias:1,por_revisar:0}},{id:'p2',etiqueta:'Plan 2',resolucion:'RES-NUEVA',resumen:{materias:1,por_revisar:0}}]}]};
const academicView={revision:0,oferta_revision:0,materias:[],plan:{id:'p1'},alcance_inscriptos:'Cátedra y período'};
const academicFixtures={'/api/planes-estudio':academicCatalog,'/api/planificacion/1/planes/p1':academicView,'/api/planificacion/1/planes/p2':academicView};
async function choosePlan(id='p1'){const el=document.querySelector('[aria-label="Carrera y versión del plan"]');assert.ok(el);await act(async()=>Simulate.change(el,{target:{value:id}}));await settle();}

afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;});

test('one explicit period is selected before any period-dependent request',async()=>{
  await mount(iea,{saved:'todos'});
  const select=document.getElementById('working-period');assert.equal(select.value,'1');
  assert.deepEqual([...select.options].map(o=>o.value),['1','2']);
  assert.ok(calls.some(u=>u.pathname==='/api/dashboard'));
  for(const url of calls.filter(u=>scoped.includes(u.pathname)))assert.equal(url.searchParams.get('cuatrimestre_id'),'1',url.href);
});

test('ambiguous calendars ask for a concrete period without loading combined data',async()=>{
  const periods=[{id:8,nombre:'Anterior 1',anio:1990,numero:1,activo:false},{id:9,nombre:'Anterior 2',anio:1990,numero:2,activo:false}];
  assert.equal(choosePeriod(periods,'todos',new Date(2026,8,12)),'');
  await mount(iea,{'/api/cuatrimestres':periods});
  assert.ok(document.getElementById('initial-period'));assert.equal(calls.filter(u=>scoped.includes(u.pathname)).length,0);
  await select('initial-period','9');assert.equal(document.getElementById('working-period').value,'9');
});

test('curriculum can be consulted without choosing an operational semester',async()=>{
  const periods=[{id:8,nombre:'Anterior 1',anio:1990,numero:1,activo:false},{id:9,nombre:'Anterior 2',anio:1990,numero:2,activo:false}];
  await mount(iea,{'/api/cuatrimestres':periods,'/api/planes-estudio':{careers:[],articulations:[],source:null}});
  await click(button('Consultar carreras y planes de estudio'));
  assert.ok(document.querySelector('.academic-catalog'));
  assert.equal(document.getElementById('working-period'),null);
  assert.equal(calls.filter(u=>scoped.includes(u.pathname)).length,0);
  assert.equal(calls.filter(u=>u.pathname==='/api/planes-estudio').length,1);
  await search('horarios por carrera');await click(document.querySelector('.app-search-item'));
  assert.ok(document.getElementById('initial-period'));
});

test('IEA tools are nested and are absent from another institution menu and search',async()=>{
  await mount(other);await search('edi');
  assert.doesNotMatch(document.querySelector('nav').textContent,/EDI por cátedra/);
  await search('BCE');assert.match(document.querySelector('nav').textContent,/0 resultados/);
  await search('asincronicas');assert.match(document.querySelector('nav').textContent,/0 resultados/);
});

test('accent-insensitive search finds IEA tertiary functions and Enter opens a result',async()=>{
  await mount();await search('iea terciarias edi');
  assert.match(document.querySelector('nav').textContent,/IEA \/ Carreras terciarias/);
  await act(async()=>Simulate.keyDown(document.querySelector('input[type="search"]'),{key:'Enter'}));await settle();
  assert.match(document.querySelector('.app-location').textContent,/EDI por cátedra/);
  await search('asincronicas');assert.match(document.querySelector('nav').textContent,/Materias asincrónicas/);
});

test('general and IEA career entries use the same catalog and period-bound planning service',async()=>{
  await mount(iea,academicFixtures);await search('horarios por carrera');
  await click(document.querySelector('.app-search-item'));await choosePlan();
  const first=calls.filter(u=>u.pathname==='/api/planificacion/1/planes/p1').at(-1);assert.ok(first);
  await search('iea horarios por carrera');await click(document.querySelector('.app-search-item'));await choosePlan();
  const second=calls.filter(u=>u.pathname==='/api/planificacion/1/planes/p1').at(-1);assert.equal(first.href,second.href);
  await click(button('Sugerencias por carrera',document.querySelector('.app-section-tabs')));
  assert.match(document.querySelector('.app-content').textContent,/Horarios por carrera y plan/);
  assert.equal(calls.filter(u=>u.pathname==='/api/plan-carrera/sugerencias').length,0);
});

test('switching periods hides old data and ignores a late response from the previous choice',async()=>{
  await mount();let resolveOld;
  handler=u=>u.pathname==='/api/catedras'&&u.searchParams.get('cuatrimestre_id')==='2'?new Promise(resolve=>{resolveOld=resolve;}):null;
  await select('working-period','2');assert.match(document.querySelector('main [role="status"]').textContent,/Periodo prueba 2/);
  assert.equal(document.querySelector('.app-content'),null);
  await select('working-period','1');assert.ok(document.querySelector('.app-content'));
  await act(async()=>resolveOld({ok:true,json:async()=>[{id:999,nombre:'RESPUESTA ANTIGUA'}]}));await settle();
  assert.equal(document.getElementById('working-period').value,'1');
  assert.doesNotMatch(document.querySelector('main').textContent,/RESPUESTA ANTIGUA/);
  assert.equal(localStorage.getItem('horarios.periodo.iea'),'1');
});

test('failed period load shows retry and never presents old data as current',async()=>{
  await mount();handler=u=>u.pathname==='/api/catedras'&&u.searchParams.get('cuatrimestre_id')==='2'?Promise.resolve({ok:false,json:async()=>({detail:'Falla de prueba'})}):null;
  await select('working-period','2');assert.match(document.querySelector('main [role="alert"]').textContent,/Falla de prueba/);assert.equal(document.querySelector('.app-content'),null);
  handler=null;await click(button('Reintentar carga'));assert.ok(document.querySelector('.app-content'));
});

test('planning opens the complete catalog without an operational period selector',async()=>{
  await mount(other,academicFixtures);await search('horarios por carrera');await click(document.querySelector('.app-search-item'));await choosePlan();
  await click(button('Abrir planes de estudio completos'));
  assert.equal(document.getElementById('working-period'),null);
  assert.match(document.querySelector('.app-content').textContent,/Carreras y planes de estudio/);
  assert.equal(calls.filter(u=>u.pathname==='/api/planes-estudio').at(-1).search,'');
});

test('switching plans preserves every plan choice and loads the selected one',async()=>{
  await mount(other,academicFixtures);await search('horarios por carrera');await click(document.querySelector('.app-search-item'));
  await choosePlan('p1');await choosePlan('p2');
  assert.deepEqual([...document.querySelector('[aria-label="Carrera y versión del plan"]').options].map(o=>o.value),['','p1','p2']);
  assert.equal(calls.filter(u=>u.pathname==='/api/planificacion/1/planes/p2').length,1);
});

test('general teachers omit manual hours and institution-specific totals',async()=>{
  await mount();await search('fichas docentes');await click(document.querySelector('.app-search-item'));
  assert.equal(document.getElementById('working-period'),null);
  const content=document.querySelector('.app-content').textContent;
  assert.match(content,/Cátedras habilitadas/);
  assert.doesNotMatch(content,/CFPEA|ISFTEA|Materias Avellaneda|Materias Caballito|Horas · Materias/);
  assert.equal(calls.filter(u=>u.pathname==='/api/docentes'&&!u.search).length,1);
});
