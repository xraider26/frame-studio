const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const out=path.resolve(__dirname,'../.studio-test/studio-page');
const built=spawnSync(process.execPath,[require.resolve('typescript/bin/tsc'),'src/app/studio/page.tsx','--outDir',out,'--jsx','react-jsx','--module','commonjs','--target','ES2023','--esModuleInterop','--skipLibCheck'],{cwd:path.resolve(__dirname,'..'),encoding:'utf8'});
assert.equal(built.status,0,built.stdout+built.stderr);
for(const file of fs.readdirSync(path.resolve(__dirname,'../src/app/studio')).filter(f=>f.endsWith('.css')))fs.copyFileSync(path.resolve(__dirname,'../src/app/studio',file),path.join(out,file));
require.extensions['.css']=()=>{};
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'http://localhost'});
Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,Node:dom.window.Node,IS_REACT_ACT_ENVIRONMENT:true});
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
const React=require('react');
const {createRoot}=require('react-dom/client');
const StudioPage=require(path.join(out,'page.js')).default;
const fixture=spawnSync(path.resolve(__dirname,'../../backend/.venv/Scripts/python.exe'),['-c',"import json,tempfile;from pathlib import Path;from studio.workflow import Studio;t=tempfile.TemporaryDirectory();r=Path(t.name);s=Studio(r/'db',r/'media',r/'inbox');p=s.create_project('Image fixture','image-custom',output_type='image');print(json.dumps(s.get_project(p['id'])))"],{cwd:path.resolve(__dirname,'../../backend'),encoding:'utf8'});
assert.equal(fixture.status,0,fixture.stderr);
const base=JSON.parse(fixture.stdout);
const caps={templates:[{id:'ai-film',name:'AI film',structure:[],output_type:'video'},{id:'image-custom',name:'Custom image',structure:[],output_type:'image'}],steps:Object.keys(base.steps).map(id=>({id,name:id})),connections:[],image_profiles:[],video_profiles:[]};
async function mount(action,overrides={}){
 const project={...base,next_action:action,...overrides};
 global.fetch=async(_url,options)=>{const {operation}=JSON.parse(options.body);let data={items:[],batches:[],instructions:''};if(operation==='studio_capabilities')data=caps;if(operation==='list_projects')data=[project];if(operation==='get_project')data=project;if(operation==='knowledge_catalog')data=null;return {ok:true,json:async()=>data};};
 const root=createRoot(document.getElementById('root'));await React.act(()=>root.render(React.createElement(StudioPage)));
 await React.act(()=>{const select=document.getElementById('project-select');select.value=project.id;select.dispatchEvent(new window.Event('change',{bubbles:true}));});
 return root;
}
const button=(text)=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
test('Continue routes an image final approval to Review without showing video import controls',async()=>{
 const root=await mount({action:'await_approval',step:'final_review',message:'Review selected images'});
 try{await React.act(()=>button('Continue').click());assert.equal(document.querySelector('[aria-current="step"]').textContent.trim().replace(/^\d+/,''),'Review');assert.ok(!document.querySelector('input[placeholder="Absolute path to your local file"]'),'Image approval must not ask for an MP4');assert.ok(document.getElementById('step-document'),'Final image notes can be prepared before approval');assert.ok(button('Approve this step'));}finally{await React.act(()=>root.unmount());}
});
test('Continue opens the brief document and five stage navigation shares a single active tool',async()=>{
 const root=await mount({action:'prepare_step',step:'brief',message:'Prepare your brief'});
 try{await React.act(()=>button('Continue').click());assert.ok(document.getElementById('step-document'));assert.equal(document.querySelectorAll('.fs-project-stages [aria-current="step"]').length,1);assert.equal(document.querySelectorAll('.fs-subnav [aria-current="page"]').length,1);await React.act(()=>button('02Plan').click());assert.equal(document.querySelector('.fs-project-stages [aria-current="step"]').textContent,'02Plan');}finally{await React.act(()=>root.unmount());}
});

test('project generators remain a single summary after repeated navigation and refresh',async()=>{
 const root=await mount({action:'quality_attention',step:'final_review',message:'Inspect images'},{generation_setup:{version:1,image:{executor:'agent_builtin',tool_name:'Built-in image tool',profile:'general_image',model:null,model_version_status:'managed',connection_id:null,selection_source:'creator_statement',source_text:'Use built-in images'}}});
 const summaries=()=>[...document.querySelectorAll('h2')].filter(el=>el.textContent==='Project generators');
 try{
  for(let i=0;i<3;i++){
   for(const stage of ['02Plan','03Create','04Review']){
    await React.act(()=>button(stage).click());
    assert.equal(summaries().length,1,`Only one project generator summary after ${stage}, pass ${i}`);
    assert.equal(document.querySelectorAll('[data-generator-question]').length,0,'Saved generators stay collapsed');
   }
   await React.act(()=>document.querySelector('[aria-label="Refresh studio"]').click());
   assert.equal(summaries().length,1,'Refresh must not retain orphan generator panels');
  }
  await React.act(()=>button('Change generator setup').click());
  await React.act(()=>{
   const input=document.querySelector('[aria-label="Image tool name"]');
   Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input,'My unsaved generator');
   input.dispatchEvent(new window.Event('input',{bubbles:true}));
  });
  for(const stage of ['03Create','04Review']){
   await React.act(()=>button(stage).click());
   assert.equal(summaries().length,1);
   assert.equal(document.querySelector('[aria-label="Image tool name"]').value,'My unsaved generator','Navigation preserves the active generator draft');
  }
  await React.act(()=>document.querySelector('[aria-label="Refresh studio"]').click());
  assert.equal(document.querySelector('[aria-label="Image tool name"]').value,'My unsaved generator');
 }finally{await React.act(()=>root.unmount());}
});
