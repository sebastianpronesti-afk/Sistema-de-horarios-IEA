// Local component checks; no requests to Railway and no production credentials.
const {test, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {JSDOM} = require('jsdom');
const {buildSync} = require('esbuild');
const dom = new JSDOM('<!doctype html><div id="root"></div>', {url:'https://audit.invalid/'});
for (const key of ['window','document','HTMLElement','Event','MouseEvent','localStorage','FormData']) global[key] = dom.window[key];
Object.defineProperty(global, 'navigator', {value:dom.window.navigator, configurable:true});
global.IS_REACT_ACT_ENVIRONMENT = true;
const React = require('react');
const {act} = require('react-dom/test-utils');
const {createRoot} = require('react-dom/client');
const built = buildSync({entryPoints:[path.join(__dirname,'../frontend/src/App.js')], bundle:true,
  loader:{'.js':'jsx'}, platform:'node', format:'cjs', external:['react'], write:false});
const compiled = new Module(path.join(__dirname, 'compiled.cjs'), module);
compiled.filename = path.join(__dirname, 'compiled.cjs');
compiled.paths = module.paths;
compiled._compile(built.outputFiles[0].text, compiled.filename);
const App = compiled.exports.default;
const example = JSON.parse(fs.readFileSync(path.join(__dirname, '../backend/app/profiles/institucion-ejemplo.json')));
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures.json')));
let root;
async function settle() {
  for (let i=0;i<5;i++) await act(async () => {await new Promise(resolve => setTimeout(resolve,15));});
}
async function mount(auth=false) {
  localStorage.clear();
  if (auth) {localStorage.setItem('iea_auth','true');localStorage.setItem('iea_rol','editor');}
  root=createRoot(document.getElementById('root'));
  await act(async () => root.render(React.createElement(App)));
  await settle();
}
afterEach(async () => {if (root) await act(async () => root.unmount());root=null;});

test('custom profile controls login title and browser title', async () => {
  global.fetch=async () => ({ok:true,json:async () => example});
  await mount();
  assert.equal(document.querySelector('h1').textContent, example.titulo);
  assert.equal(document.title, example.titulo);
});

test('configuration failure blocks the application and permits retry', async () => {
  let failed=true;
  global.fetch=async () => ({ok:!failed,json:async () => example});
  await mount(true);
  assert.match(document.querySelector('[role="alert"]').textContent, /No se pudo cargar/);
  assert.equal(document.querySelector('nav'), null);
  failed=false;
  localStorage.clear();
  await act(async () => document.querySelector('button').click());
  await settle();
  assert.equal(document.querySelector('h1').textContent, example.titulo);
});

test('malformed profile does not silently apply default IEA rules', async () => {
  global.fetch=async () => ({ok:true,json:async () => ({...example,alumnos_por_docente:0})});
  await mount();
  assert.ok(document.querySelector('[role="alert"]'));
  assert.equal(document.querySelector('input[type="password"]'), null);
});

test('custom opening threshold is shown in the existing decisions section', async () => {
  global.fetch=async url => {
    const key=new URL(url,'https://audit.invalid').pathname;
    return {ok:true,json:async () => structuredClone(key === '/api/institucion' ? example : fixtures[key] ?? {})};
  };
  await mount(true);
  const offer=[...document.querySelectorAll('nav button')].find(b=>b.textContent==='Oferta y materias');
  await act(async()=>offer.click());await settle();
  const button=[...document.querySelectorAll('nav button')].find(b => /Decisiones/.test(b.textContent));
  assert.ok(button);
  await act(async () => button.click());
  await settle();
  assert.match(document.querySelector('main').textContent, /≥15/);
  assert.doesNotMatch(document.querySelector('main').textContent, /≥10/);
});

test('assignment form preserves an institutional duration outside the fixed half-hour grid', async () => {
  global.fetch=async url => {
    const key=new URL(url,'https://audit.invalid').pathname;
    return {ok:true,json:async () => structuredClone(key === '/api/institucion'
      ? {...example, duracion_clase_minutos:45} : fixtures[key] ?? {})};
  };
  await mount(true);
  const offer=[...document.querySelectorAll('nav button')].find(b=>b.textContent==='Oferta y materias');
  await act(async()=>offer.click());await settle();
  const nav=[...document.querySelectorAll('nav button')].find(b=>b.textContent==='Materias y asignaciones');
  await act(async () => nav.click());
  await settle();
  const add=[...document.querySelectorAll('main button')].find(b => b.textContent.trim() === '+');
  assert.ok(add);
  await act(async () => add.click());
  await settle();
  const field = text => [...document.querySelectorAll('label')]
    .find(label => label.textContent === text).parentElement.querySelector('select');
  const start=field('Comienza:');
  await act(async () => {start.value='18:00';start.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(field('Termina:').value, '18:45');
});
