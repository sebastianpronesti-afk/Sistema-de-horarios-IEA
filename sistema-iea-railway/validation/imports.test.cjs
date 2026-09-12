// User interaction tests with synthetic responses; never contact production.
const {test,afterEach}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const Module=require('node:module');
const {JSDOM}=require('jsdom');
const {buildSync}=require('esbuild');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://validation.invalid'});
for(const key of ['window','document','HTMLElement','Event','MouseEvent','FormData'])global[key]=dom.window[key];
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react');
const {act}=require('react-dom/test-utils');
const {createRoot}=require('react-dom/client');
const built=buildSync({entryPoints:[path.join(__dirname,'../frontend/src/ImportWorkflow.js')],bundle:true,
  loader:{'.js':'jsx'},platform:'node',format:'cjs',external:['react'],write:false});
const compiled=new Module(path.join(__dirname,'imports.compiled.cjs'),module);
compiled.filename=path.join(__dirname,'imports.compiled.cjs');compiled.paths=module.paths;
compiled._compile(built.outputFiles[0].text,compiled.filename);
const Workflow=compiled.exports.default, History=compiled.exports.ImportHistory;
let root, calls, responsePreview, history=[];
const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent===label);
const field=label=>document.querySelector(`[aria-label="${label}"]`);
const settle=async()=>{await act(async()=>{await new Promise(resolve=>setTimeout(resolve,5));});};
async function change(element,value){await act(async()=>{element.value=value;element.dispatchEvent(new Event('change',{bubbles:true}));});await settle();}
async function click(element){await act(async()=>element.click());await settle();}
async function mount(Component=Workflow,extra={}){
  calls=[];
  responsePreview={archivo:'prueba.xlsx',alcance:{sede:'Caballito'},resumen:{altas:1,modificaciones:0,bajas:0,sin_cambios:0,cambios_relacionados:0},
    columnas:['Subject','Campus','Weekday','Begin'],errores:[],advertencias:[],cambios:[],puede_aplicar:true,token:'test-token'};
  global.fetch=async(url,options={})=>{
    calls.push({url,options});
    const data=url.includes('/historial')?{historial:history}:url.includes('/aplicar')?{historial_id:7}:responsePreview;
    return {ok:true,json:async()=>structuredClone(data)};
  };
  root=createRoot(document.getElementById('root'));
  await act(async()=>root.render(React.createElement(Component,{periods:[{id:1,nombre:'Prueba'}],campuses:[{id:1,nombre:'Caballito'}],initialPeriod:1,...extra})));
  await settle();
}
async function selectFile(){
  await change(field('Sede de importación'),'1');
  const input=field('Archivo a importar');
  Object.defineProperty(input,'files',{value:[new dom.window.File(['synthetic'],'prueba.xlsx')],configurable:true});
  await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));
  await settle();
}
afterEach(async()=>{if(root)await act(async()=>root.unmount());root=null;history=[];});

test('requires an explicit campus and sends preview token when applying',async()=>{
  await mount();
  assert.equal(button('Analizar y ver diferencias').disabled,true);
  await selectFile();await click(button('Analizar y ver diferencias'));
  assert.equal(button('Confirmar y aplicar cambios').disabled,false);
  await click(button('Confirmar y aplicar cambios'));
  const apply=calls.find(c=>c.url.includes('/aplicar'));
  assert.equal(apply.options.body.get('token'),'test-token');
  assert.match(apply.url,/sede_id=1/);
  assert.match(document.querySelector('[role="status"]').textContent,/#7/);
});

test('deletions require acknowledgement and changing scope invalidates the preview',async()=>{
  await mount();await selectFile();responsePreview.resumen.bajas=2;
  await click(button('Analizar y ver diferencias'));
  assert.equal(button('Confirmar y aplicar cambios').disabled,true);
  await click(document.querySelector('input[type="checkbox"]'));
  assert.equal(button('Confirmar y aplicar cambios').disabled,false);
  await change(field('Sede de importación'),'0');
  assert.equal(button('Confirmar y aplicar cambios'),undefined);
});

test('invalid rows block confirmation and several manual mappings can be edited',async()=>{
  await mount();await selectFile();
  responsePreview.puede_aplicar=false;responsePreview.token=null;
  responsePreview.errores=[{hoja:'Datos',fila:2,mensaje:'Falta el código de materia'}];
  await click(button('Analizar y ver diferencias'));
  assert.equal(button('Confirmar y aplicar cambios').disabled,true);
  assert.match(document.querySelector('[role="alert"]').textContent,/Falta el código/);
  const mapper=label=>[...document.querySelectorAll('details label')].find(l=>l.firstChild.textContent===label).querySelector('select');
  await change(mapper('Código de materia'),'Subject');
  assert.equal(button('Confirmar y aplicar cambios'),undefined);
  await change(mapper('Sede'),'Campus');
  await click(button('Analizar y ver diferencias'));
  const last=calls.filter(c=>c.url.includes('vista-previa')).at(-1);
  assert.deepEqual(JSON.parse(last.options.body.get('mapeo')),{codigo_materia:'Subject',sede:'Campus'});
});

test('consulta mode cannot invoke imports',async()=>{
  await mount(Workflow,{canEdit:false});await selectFile();
  assert.equal(button('Analizar y ver diferencias').disabled,true);
  assert.equal(calls.filter(c=>c.options.method==='POST').length,0);
});

test('recovery conflicts block confirmation and a stale response prompts review again',async()=>{
  history=[{id:7,tipo:'horarios',archivo:'prueba.xlsx',cuatrimestre_id:1,sede_id:1}];
  await mount(History,{period:1});
  let conflict=true;
  global.fetch=async url=>({ok:!url.endsWith('/restaurar'),json:async()=>url.endsWith('/restaurar')
    ?{detail:'La vista previa venció. Volvé a analizar.'}
    :{historial_id:7,puede_restaurar:!conflict,conflictos:conflict?['El horario fue modificado después']:[],cambios:[],token:'restore-token'}});
  await click(button('Revisar recuperación'));
  assert.equal(button('Confirmar recuperación').disabled,true);
  conflict=false;await click(button('Revisar recuperación'));
  assert.equal(button('Confirmar recuperación').disabled,false);
  await click(button('Confirmar recuperación'));
  assert.match(document.querySelector('[role="alert"]').textContent,/Volvé a analizar/);
  assert.equal(button('Confirmar recuperación'),undefined);
});
