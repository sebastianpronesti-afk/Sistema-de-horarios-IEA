const {test,afterEach}=require('node:test'),assert=require('node:assert/strict');
const path=require('node:path'),Module=require('node:module');
const {JSDOM}=require('jsdom'),{buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const k of ['window','document','HTMLElement','Event','MouseEvent','localStorage'])global[k]=dom.window[k];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react'),{act,Simulate}=require('react-dom/test-utils'),{createRoot}=require('react-dom/client');
function compile(file){const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src',file)],bundle:true,loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});const mod=new Module(path.join(__dirname,file+'.cjs'),module);mod.filename=path.join(__dirname,file+'.cjs');mod.paths=module.paths;mod._compile(built.outputFiles[0].text,mod.filename);return mod.exports.default;}
const Planning=compile('CurriculumPlanning.js'),Enrollment=compile('EnrollmentPlans.js');
const catalog={careers:[{id:'career',nombre:'Carrera conocida',planes:[{id:'p1',etiqueta:'Plan 1'},{id:'p2',etiqueta:'Plan 2'}]}]};
const view={plan:{id:'p1'},revision:0,oferta_revision:0,estado_oferta:'sin_configurar',alcance_inscriptos:'Cátedra y período',materias:[{
  id:'s1',nombre:'Materia existente',anio:1,cuatrimestre:2,catedra:{id:1,codigo:'c.1',nombre:'Cátedra existente'},
  ofertada:false,inscriptos:20,criterio:'ABRIR',docentes_requeridos:1,detalle_inscriptos:{plan_pendiente:20},
  asignaciones:[{id:7,docente:'Docente ficticio',dia:'Lunes',hora_inicio:'09:00',hora_fin:'10:30'}]
}]};
const course={curso_id:1,carrera_informada:'Carrera tal como fue importada',career_id:'career',revision:1,source_token:'source',alumnos:1,planes_confirmados:0,planes_pendientes:1};
const index={courses:[course],careers:catalog.careers,catalog_revision:0};
const students={course,catalog_revision:0,total:1,rows:[{alumno_id:1,nombre:'Alumno ficticio',dni:'99000001',curso_id:1,
  career_id:'career',plan_id:null,revision:0,course_revision:1,source_token:'student-source',catedra_ids:[1],nota:''}]};
let root,requests,handler;
const settle=async()=>{for(let i=0;i<3;i++)await act(async()=>new Promise(r=>setTimeout(r,2)));};
async function mount(Component,props={}){
  requests=[];handler=null;
  global.fetch=async(url,options={})=>{
    requests.push([url,options]);if(handler){const r=handler(url,options);if(r)return await r;}
    const path=url.split('?')[0];
    const value=path==='/api/planes-estudio'?catalog:path==='/api/sedes'?[]:path.startsWith('/api/planificacion/')?view:
      path==='/api/inscripciones-planes/1'?index:path.includes('/cursos/')?students:{};
    return {ok:true,json:async()=>structuredClone(value)};
  };
  root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(Component,{cuatrimestre:1,onCatalog:()=>{},...props})));await settle();
}
async function change(el,value){assert.ok(el);await act(async()=>Simulate.change(el,{target:{value}}));await settle();}
async function click(text){const b=[...document.querySelectorAll('button')].find(b=>b.textContent===text);assert.ok(b,text);await act(async()=>b.click());await settle();}
afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;});
test('unconfigured read-only planning shows existing references and explains why editing is unavailable',async()=>{
  await mount(Planning);await change(document.querySelector('[aria-label="Carrera y versión del plan"]'),'p1');
  assert.match(document.body.textContent,/Todavía no se confirmó la oferta/);
  assert.match(document.body.textContent,/Estás en modo consulta/);
  assert.match(document.body.textContent,/Materia existente/);assert.match(document.body.textContent,/Docente ficticio/);
  assert.match(document.body.textContent,/Referencia · no ofrecida/);
  assert.equal([...document.querySelectorAll('button')].some(b=>b.textContent==='Configurar materias de este período'),false);
  assert.equal(requests.some(([,o])=>o.method),false);
});
test('reference rows are not silently offered; an editor must select and save',async()=>{
  await mount(Planning,{puedeEditar:true});await change(document.querySelector('select'),'p1');
  await click('Configurar materias de este período');
  const checkbox=document.querySelector('[aria-label="Ofrecer Materia existente"]');assert.equal(checkbox.checked,false);
  await act(async()=>Simulate.change(checkbox,{target:{checked:true}}));
  await change(document.querySelector('input[type=password]'),'fixture-editor-only');await click('Guardar oferta del período');
  const writes=requests.filter(([,o])=>o.method==='PUT');assert.equal(writes.length,1);
  assert.deepEqual(JSON.parse(writes[0][1].body).materia_ids,['s1']);
});
test('a known career leaves a student plan pending until explicit confirmation',async()=>{
  await mount(Enrollment,{puedeEditar:true});await change(document.querySelector('[aria-label="Carrera o curso informado"]'),'1');
  assert.match(document.body.textContent,/Carrera tal como fue importada/);
  assert.match(document.body.textContent,/Plan pendiente de validar/);
  const studentSelect=[...document.querySelectorAll('select')].find(e=>e.parentElement.textContent.startsWith('Plan de Alumno'));
  assert.equal(studentSelect.value,'');assert.deepEqual([...studentSelect.options].map(o=>o.value),['','p1','p2']);
  assert.equal(requests.some(([,o])=>o.method),false);
  await change(studentSelect,'p2');await change(document.querySelector('input[type=password]'),'fixture-editor-only');
  await click('Guardar validación');
  const body=JSON.parse(requests.find(([,o])=>o.method==='PUT')[1].body);
  assert.equal(body.plan_id,'p2');assert.equal(body.course_revision,1);assert.equal(body.source_token,'student-source');
});
test('consultation can inspect pending student plans without exposing save controls',async()=>{
  await mount(Enrollment);await change(document.querySelector('select'),'1');
  assert.match(document.body.textContent,/Modo consulta/);assert.match(document.body.textContent,/Plan pendiente de validar/);
  assert.equal(document.querySelector('input[type=password]'),null);
  assert.equal([...document.querySelectorAll('button')].some(b=>b.textContent==='Guardar validación'),false);
});
