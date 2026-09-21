const {test,afterEach}=require('node:test'),assert=require('node:assert/strict');
const path=require('node:path'),Module=require('node:module');
const {JSDOM}=require('jsdom'),{buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const k of ['window','document','HTMLElement','Event','MouseEvent','localStorage'])global[k]=dom.window[k];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react'),{act,Simulate}=require('react-dom/test-utils'),{createRoot}=require('react-dom/client');
function compile(file){const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src',file)],bundle:true,loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});const mod=new Module(path.join(__dirname,file+'.cjs'),module);mod.filename=path.join(__dirname,file+'.cjs');mod.paths=module.paths;mod._compile(built.outputFiles[0].text,mod.filename);return mod.exports;}
const {PlanEditor,rememberEditorKey}=compile('AcademicEditors.js');
const IdentityReview=compile('IdentityReview.js').default;
let root,requests,saved;
const settle=async()=>{for(let i=0;i<3;i++)await act(async()=>new Promise(r=>setTimeout(r,2)));};
async function mount(Component,props){root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(Component,props)));await settle();}
afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;rememberEditorKey('');});
test('plan identity is visible and immutable while academic version is editable',async()=>{
  requests=[];saved=false;rememberEditorKey('fixture-only');
  global.fetch=async(url,opts)=>{requests.push(JSON.parse(opts.body));return {ok:true,json:async()=>({ok:true,revision:3})};};
  await mount(PlanEditor,{plan:{id:'permanent-plan',etiqueta:'Plan 1',materias:[]},revision:2,onSaved:()=>saved=true,onClose:()=>{}});
  assert.match(document.querySelector('code').textContent,/permanent-plan/);
  const label=[...document.querySelectorAll('label')].find(l=>l.textContent.startsWith('Versión dentro'));
  assert.equal(label.querySelector('input').value,'1');
  await act(async()=>Simulate.change(label.querySelector('input'),{target:{value:'2'}}));
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Guardar plan').click());await settle();
  assert.equal(requests[0].plan_id,'permanent-plan');assert.equal(requests[0].changes.version_plan,'2');
  assert.equal('id' in requests[0].changes,false);assert.equal(saved,true);
});
test('review identifies possible duplicates without exposing a merge operation',async()=>{
  let selected=null;
  global.fetch=async()=>({ok:true,json:async()=>({documentos_repetidos:[[1,2]],nombres_coincidentes:[[1,2]],docentes_sin_documento_valido:[3],codigos_repetidos:[]})});
  await mount(IdentityReview,{kind:'docentes',onTeacher:id=>selected=id});
  assert.match(document.body.textContent,/DOC-000001/);assert.match(document.body.textContent,/personas distintas/);
  const button=document.querySelector('button');await act(async()=>button.click());assert.equal(selected,1);
  assert.ok([...document.querySelectorAll('button')].every(b=>b.textContent.startsWith('DOC-')));
});
test('failed identity report does not claim there are no duplicates',async()=>{
  global.fetch=async()=>({ok:false});await mount(IdentityReview,{kind:'catedras'});
  assert.match(document.querySelector('[role=alert]').textContent,/No se pudo/);
  assert.doesNotMatch(document.body.textContent,/No se encontraron/);
});
