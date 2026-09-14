const {test,afterEach}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path'),Module=require('node:module');
const {JSDOM}=require('jsdom'),{buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const k of ['window','document','HTMLElement','Event','MouseEvent','localStorage'])global[k]=dom.window[k];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react'),{act,Simulate}=require('react-dom/test-utils'),{createRoot}=require('react-dom/client');
const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src/AcademicPlans.js')],bundle:true,loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});
const mod=new Module(path.join(__dirname,'AcademicPlans.cjs'),module);mod.filename=path.join(__dirname,'AcademicPlans.cjs');mod.paths=module.paths;mod._compile(built.outputFiles[0].text,mod.filename);
const Component=mod.exports.default;
const plan={id:'p1',etiqueta:'Plan 1',nombre_oficial:'Tecnicatura de prueba',resolucion:'RES-TEST',modalidad:'presencial',jurisdiccion:'CABA',situacion:'por_confirmar',observaciones:[],resumen:{materias:2,vinculadas:1,por_revisar:1}};
const career={id:'c1',nombre:'Administración de prueba',nivel:'terciario',planes:[plan],materias_sin_plan:1};
const catalog={careers:[career,{id:'c2',nombre:'Secundario de prueba',nivel:'secundario',planes:[{...plan,id:'p2',modalidad:'distancia',jurisdiccion:null}],materias_sin_plan:0}],articulations:[{id:'a1',nombre:'Doble titulación de prueba',materias:0}],source:{filename:'Prueba.xlsx',revision:'2026-09-14'}};
const detail={...plan,carrera:career.nombre,materias:[{id:'s1',nombre:'Materia correcta',anio:1,cuatrimestre:2,codigo_archivo:'c.1',vinculo:{estado:'coincide',catedra:{codigo:'c.1',nombre:'Materia correcta'}},observaciones:[],origen:{hoja:'Prueba',fila:10}},
{id:'s2',nombre:'Materia por revisar',anio:null,cuatrimestre:null,codigo_archivo:'c.9',vinculo:{estado:'revisar_asociacion',catedra:null,candidatas:[{id:9,codigo:'c.9',nombre:'Otra materia'}]},observaciones:['Revisar nombre'],origen:{hoja:'Prueba',fila:11}}]};
let root,requests,handler;
const settle=async()=>{for(let i=0;i<3;i++)await act(async()=>new Promise(r=>setTimeout(r,2)));};
const buttons=()=>[...document.querySelectorAll('button')];
async function click(text){const button=buttons().find(b=>b.textContent.includes(text));assert.ok(button,text);await act(async()=>button.click());await settle();}
async function change(el,value){await act(async()=>Simulate.change(el,{target:{value}}));await settle();}
async function mount(data=catalog,props={}){
  requests=[];handler=null;
  global.fetch=async(url,options)=>{requests.push([url,options]);if(handler){const result=handler(url);if(result)return result;}
    const result=url==='/api/planes-estudio'?data:url.includes('/articulaciones/')?{nombre:'Doble titulación de prueba',observaciones:[],bloques:[]}:url.includes('/pendientes')?{nombre:'Pendientes',materias:detail.materias}:{...detail,id:url.split('/').at(-1)};
    return {ok:true,json:async()=>structuredClone(result)};};
  root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(Component,props)));await settle();
}
afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;});

test('search and independent modality/jurisdiction filters retain correct plans',async()=>{
  await mount();await change(document.querySelector('input[type=search]'),'administracion');
  assert.equal(document.querySelectorAll('.academic-plan-card').length,1);
  await change(document.querySelector('input[type=search]'),'');
  await change(document.querySelectorAll('select')[1],'distancia');
  assert.equal(document.querySelectorAll('.academic-plan-card').length,1);assert.match(document.querySelector('.academic-career').textContent,/Secundario de prueba/);
});

test('detail preserves existing codes and explicitly marks missing academic fields',async()=>{
  await mount();await click('Plan 1 · RES-TEST');
  assert.match(document.body.textContent,/2° cuatrimestre/);assert.match(document.body.textContent,/Año pendiente/);
  assert.match(document.body.textContent,/Cátedra a revisar: c.9/);
  const checkbox=document.querySelector('input[type=checkbox]');await act(async()=>Simulate.change(checkbox,{target:{checked:true}}));await settle();
  assert.equal(document.querySelectorAll('tbody tr').length,1);
  assert.match(document.querySelector('tbody').textContent,/Materia por revisar/);
  assert.ok(requests.every(([,options])=>!options.method||options.method==='GET'));
});

test('empty institution does not invent or show IEA data',async()=>{
  await mount({careers:[],articulations:[],source:null});assert.match(document.body.textContent,/todavía no tiene un catálogo/);
  assert.equal(document.querySelectorAll('.academic-plan-card').length,0);
});

test('review filter includes missing academic data even when the subject code matches',async()=>{
  await mount();
  handler=url=>url.endsWith('/p1')?Promise.resolve({ok:true,json:async()=>({...detail,materias:[
    {...detail.materias[0],anio:null,observaciones:[]},
    {...detail.materias[0],id:'edi',nombre:'EDI',vinculo:{estado:'espacio_edi'},observaciones:[]}
  ]})}):null;
  await click('Plan 1 · RES-TEST');
  await act(async()=>Simulate.change(document.querySelector('input[type=checkbox]'),{target:{checked:true}}));await settle();
  assert.equal(document.querySelectorAll('tbody tr').length,1);
  assert.match(document.querySelector('tbody').textContent,/Año pendiente/);
  assert.doesNotMatch(document.querySelector('tbody').textContent,/Espacio EDI/);
});

test('secondary entry applies its initial filter without duplicating the catalog',async()=>{
  await mount(catalog,{initialLevel:'secundario'});assert.equal(document.querySelectorAll('.academic-plan-card').length,1);
  assert.match(document.querySelector('.academic-career').textContent,/Secundario/);
});

test('articulations and unassigned subjects have visible review paths',async()=>{
  await mount();await click('Revisar 1 materias sin plan');assert.match(document.body.textContent,/Pendientes/);
  await click('Volver al catálogo');await click('Dobles titulaciones');await click('Doble titulación de prueba');
  assert.match(document.body.textContent,/no incluye el detalle de sus materias/);
});

test('late detail response never replaces a later selection',async()=>{
  await mount();let resolve;
  handler=url=>url.endsWith('/p1')?new Promise(r=>resolve=r):null;
  await click('Plan 1 · RES-TEST');assert.match(document.body.textContent,/Cargando detalle/);
  await click('Volver al catálogo');handler=null;
  await act(async()=>document.querySelectorAll('.academic-plan-card')[1].click());await settle();
  await act(async()=>resolve({ok:true,json:async()=>({...detail,carrera:'DETALLE ANTIGUO'})}));await settle();
  assert.doesNotMatch(document.body.textContent,/DETALLE ANTIGUO/);
});

test('failed detail is explicit and can be retried',async()=>{
  await mount();handler=url=>url.endsWith('/p1')?Promise.resolve({ok:false,json:async()=>({detail:'Error de prueba'})}):null;
  await click('Plan 1 · RES-TEST');assert.match(document.querySelector('[role=alert]').textContent,/Error de prueba/);
  handler=null;await click('Reintentar detalle');assert.ok(document.querySelector('table'));
});
