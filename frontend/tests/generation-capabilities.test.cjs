const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const frontend=path.resolve(__dirname,'..');
const backend=path.resolve(frontend,'../backend');
const python=path.join(backend,'.venv/Scripts/python.exe');
const out=path.join(frontend,'.studio-test/generation-capabilities');
const built=spawnSync(process.execPath,[require.resolve('typescript/bin/tsc'),'src/app/studio/production-workspace.tsx','--outDir',out,'--jsx','react-jsx','--module','commonjs','--target','ES2023','--esModuleInterop','--skipLibCheck'],{cwd:frontend,encoding:'utf8'});
assert.equal(built.status,0,built.stdout+built.stderr);
const fixture=spawnSync(python,['-c',"import json,tempfile;from pathlib import Path;from studio.workflow import Studio;t=tempfile.TemporaryDirectory();r=Path(t.name);s=Studio(r/'db',r/'media',r/'inbox');p=s.create_project('Capability fixture','custom');print(json.dumps(s.get_project(p['id'])))"],{cwd:backend,encoding:'utf8'});
assert.equal(fixture.status,0,fixture.stderr);
const base=JSON.parse(fixture.stdout);
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'http://localhost'});
Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,Node:dom.window.Node,IS_REACT_ACT_ENVIRONMENT:true});
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
const React=require('react');
const {createRoot}=require('react-dom/client');
const {ProductionWorkspace}=require(path.join(out,'production-workspace.js'));
let requests=[];
global.fetch=async(_url,options)=>{const request=JSON.parse(options.body);requests.push(request);return {ok:true,json:async()=>({})};};
const legacy={...base.production.capabilities,model:'Stale combined model',confirmed:true,source:'Old combined evidence',observed_at:'2026-10-24',aspects:['16:9']};
const video={...base.production.capabilities,model:'Video tool',confirmed:true,source:'Video evidence',observed_at:'2026-10-24',aspects:['16:9']};
function project(adopt=true,imageOnly=false){const p=structuredClone(base);p.revision=7;p.output_type=imageOnly?'image':'video';p.production.capabilities=structuredClone(legacy);p.production.capabilities_by_kind.video=structuredClone(video);if(adopt)p.generation_setup={version:1,image:{executor:'agent_builtin',tool_name:'Image tool',profile:'general_image',model:null,model_version_status:'managed',connection_id:null,selection_source:'creator_statement',source_text:'Use the image tool'}};return p;}
const props=p=>({project:p,view:'production',busy:false,catalog:null,save:async fn=>fn()});
const field=label=>{const l=[...document.querySelectorAll('label')].find(l=>l.textContent.trim()===label);assert.ok(l,label);return l.htmlFor?document.getElementById(l.htmlFor):l.querySelector('input,select');};
async function input(label,value){await React.act(()=>{const el=field(label);Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el,value);el.dispatchEvent(new window.Event('input',{bubbles:true}));});}
async function click(label){await React.act(async()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);assert.ok(b,label);b.click();});}
async function medium(value){await React.act(()=>{const select=document.querySelector('[aria-label="Capability medium"]');assert.ok(select,'Image/video observation selector');select.value=value;select.dispatchEvent(new window.Event('change',{bubbles:true}));});}
function applyToApi(p,request){
 const script="import json,sys,tempfile;from pathlib import Path;from fastapi.testclient import TestClient;from studio.api import create_app;from studio.preflight import preflight;data=json.load(sys.stdin);t=tempfile.TemporaryDirectory();app=create_app(Path(t.name),'agent','human');app.state.studio.insert(data['project']);response=TestClient(app).post('/studio/v1/command',json=data['request'],headers={'Authorization':'Bearer human'});p=app.state.studio.get(data['project']['id']);print(json.dumps({'status':response.status_code,'response':response.json(),'image':preflight(p,p['shots'][0]['id'],'image'),'video':preflight(p,p['shots'][0]['id'],'video')}))";
 const result=spawnSync(python,['-c',script],{cwd:backend,encoding:'utf8',input:JSON.stringify({project:p,request})});assert.equal(result.status,0,result.stderr);const data=JSON.parse(result.stdout);assert.equal(data.status,200,JSON.stringify(data.response));return data;
}

test('adopted capability editor saves per-medium observations enforced by actual API preflight',async()=>{
 window.sessionStorage.clear();window.localStorage.clear();requests=[];let p=project();const root=createRoot(document.getElementById('root'));
 try{
  await React.act(()=>root.render(React.createElement(ProductionWorkspace,props(p))));
  assert.equal(field('I checked these controls in the specified generator').checked,false,'Retained legacy evidence must not appear confirmed for the image tool');
  assert.equal(field('Model / version').value,'');
  assert.ok(![...document.querySelectorAll('label')].some(l=>l.textContent.trim()==='Supported clip durations (comma separated)'),'Image observations omit video durations');
  await input('Model / version','Observed image tool');await input('Observation source / evidence','Image tool UI');await input('Observed date','2026-10-24');await input('Supported aspect ratios (comma separated)','9:16');
  await React.act(()=>field('I checked these controls in the specified generator').click());
  await click('Apply production settings');
  let request=requests.find(r=>r.operation==='update_production');assert.ok(request);assert.equal(request.arguments.expected_revision,7);assert.deepEqual(request.arguments.production.capabilities,legacy);assert.deepEqual(request.arguments.production.capabilities_by_kind.image.aspects,['9:16']);assert.deepEqual(request.arguments.production.capabilities_by_kind.video,video);
  let result=applyToApi(p,request);assert.ok(result.image.issues.some(i=>i.rule==='unsupported_aspect'));assert.ok(!result.video.issues.some(i=>i.rule==='unsupported_aspect'));
  p=result.response;requests=[];await React.act(()=>root.render(React.createElement(ProductionWorkspace,props(p))));
  await medium('video');assert.equal(field('Model / version').value,'Video tool');assert.ok(field('Supported clip durations (comma separated)'));
  await input('Supported aspect ratios (comma separated)','1:1');await click('Apply production settings');
  request=requests.find(r=>r.operation==='update_production');assert.deepEqual(request.arguments.production.capabilities_by_kind.image.aspects,['9:16']);assert.deepEqual(request.arguments.production.capabilities_by_kind.video.aspects,['1:1']);result=applyToApi(p,request);assert.ok(result.video.issues.some(i=>i.rule==='unsupported_aspect'));
 }finally{await React.act(()=>root.unmount());}
});

test('legacy capability editor retains combined evidence and image-only setup exposes no video medium',async()=>{
 window.sessionStorage.clear();requests=[];const p=project(false);let root=createRoot(document.getElementById('root'));
 try{await React.act(()=>root.render(React.createElement(ProductionWorkspace,props(p))));assert.equal(field('Model / version').value,'Stale combined model');assert.equal(field('I checked these controls in the specified generator').checked,true);assert.ok(!document.querySelector('[aria-label="Capability medium"]'));await input('Supported aspect ratios (comma separated)','4:5');await click('Apply production settings');const request=requests.find(r=>r.operation==='update_production');assert.deepEqual(request.arguments.production.capabilities.aspects,['4:5']);assert.equal(request.arguments.production.capabilities_by_kind.image.confirmed,false);}finally{await React.act(()=>root.unmount());}
 window.sessionStorage.clear();root=createRoot(document.getElementById('root'));try{await React.act(()=>root.render(React.createElement(ProductionWorkspace,props(project(true,true)))));assert.ok(!document.querySelector('[aria-label="Capability medium"]'));assert.equal(field('Model / version').value,'');}finally{await React.act(()=>root.unmount());}
});
