const {test,afterEach}=require('node:test'),assert=require('node:assert/strict');
const path=require('node:path'),Module=require('node:module');
const {JSDOM}=require('jsdom'),{buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const k of ['window','document','HTMLElement','Event','MouseEvent','localStorage'])global[k]=dom.window[k];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react'),{act,Simulate}=require('react-dom/test-utils'),{createRoot}=require('react-dom/client');
function compile(file){const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src',file)],bundle:true,loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});const mod=new Module(path.join(__dirname,file+'.cjs'),module);mod.filename=path.join(__dirname,file+'.cjs');mod.paths=module.paths;mod._compile(built.outputFiles[0].text,mod.filename);return mod.exports;}
const {SubjectEditor,rememberEditorKey}=compile('AcademicEditors.js');
const subject={id:'s1',nombre:'Materia de prueba',anio:1,cuatrimestre:2,catedra_id:1,correlativa_ids:[]};
const plan={id:'p1',materias:[subject,{id:'s2',nombre:'Materia previa'}]};
let root,requests,saved;
const settle=async()=>{for(let i=0;i<3;i++)await act(async()=>new Promise(r=>setTimeout(r,2)));};
async function mount(extra={}){
  requests=[];saved=false;rememberEditorKey('fixture-editor-only');
  global.fetch=async(url,options={})=>{requests.push([url,options]);return {ok:true,json:async()=>url.includes('/opciones')?{catedras:[{id:1,codigo:'c.1',nombre:'Cátedra uno'},{id:2,codigo:'c.2',nombre:'Cátedra dos'}]}:url.endsWith('/p2')?{id:'p2',materias:[{id:'s3',nombre:'Materia del plan destino'}]}:{ok:true,revision:2}};};
  root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(SubjectEditor,{subject,plan,revision:1,onSaved:()=>{saved=true;},onClose:()=>{},...extra})));await settle();
}
async function change(el,value){await act(async()=>Simulate.change(el,{target:{value}}));await settle();}
async function click(text){const b=[...document.querySelectorAll('button')].find(b=>b.textContent===text);assert.ok(b);await act(async()=>b.click());await settle();}
afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;rememberEditorKey('');});
test('subject editor stores chair identifiers and separate year and semester with same-plan prerequisites',async()=>{
  await mount();const numbers=document.querySelectorAll('input[type=number]');assert.equal(numbers.length,2);
  await change(numbers[0],'3');await change(numbers[1],'1');
  const options=[...document.querySelectorAll('input[type=checkbox]')];assert.equal(options.length,1);assert.match(options[0].parentElement.textContent,/Materia previa/);
  await act(async()=>Simulate.change(options[0],{target:{checked:true}}));
  await change(document.querySelector('select'),'2');await click('Guardar materia');
  const body=JSON.parse(requests.find(([url,opts])=>opts.method==='POST')[1].body);
  assert.equal(body.operation,'subject');assert.equal(body.revision,1);
  assert.deepEqual(body.changes.correlativa_ids,['s2']);
  assert.equal(body.changes.anio,3);assert.equal(body.changes.cuatrimestre,1);assert.equal(body.changes.catedra_id,2);assert.equal(saved,true);
});
test('moving a pending subject only offers destination plans from its career and clears old prerequisites',async()=>{
  await mount({subject:{...subject,correlativa_ids:['s2']},plan:null,career:{id:'career',planes:[{id:'p2',etiqueta:'Destino',resolucion:'RES'}]}});
  const selector=document.querySelector('select');assert.deepEqual([...selector.options].map(o=>o.value),['','p2']);
  await change(selector,'p2');assert.match(document.querySelector('fieldset').textContent,/Materia del plan destino/);
  assert.equal(document.querySelector('input[type=checkbox]').checked,false);
  await click('Guardar materia');
  const body=JSON.parse(requests.find(([,o])=>o.method==='POST')[1].body);
  assert.equal(body.operation,'move');assert.equal(body.plan_id,'p2');assert.deepEqual(body.changes.correlativa_ids,[]);
});
test('conflicting save remains open and displays the server explanation',async()=>{
  await mount();global.fetch=async()=>({ok:false,json:async()=>({detail:'El catálogo cambió. Recargá antes de guardar.'})});
  await click('Guardar materia');assert.equal(saved,false);assert.match(document.querySelector('[role=alert]').textContent,/catálogo cambió/);
});
test('a pending subject can select any chair and save while its destination plan stays unknown',async()=>{
  await mount({subject:{id:'pending',nombre:'Pendiente',vinculo:{candidatas:[]}},plan:null,career:{id:'career',planes:[]}});
  const selectors=document.querySelectorAll('select');
  assert.equal(selectors[0].value,'');assert.equal(selectors[1].options.length,3);
  await change(selectors[1],'2');await click('Guardar materia');
  const body=JSON.parse(requests.find(([,o])=>o.method==='POST')[1].body);
  assert.equal(body.operation,'pending_subject');assert.equal(body.changes.catedra_id,2);
  assert.equal(body.plan_id,'');assert.equal('correlativa_ids' in body.changes,false);assert.equal(saved,true);
});
