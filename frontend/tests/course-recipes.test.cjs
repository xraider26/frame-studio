const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { JSDOM } = require('jsdom');
const compiled = path.resolve(__dirname, '../.studio-test/course-recipes');
const built = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'), 'src/app/studio/recipe-workspace.tsx', '--outDir', compiled, '--jsx', 'react-jsx', '--module', 'commonjs', '--target', 'ES2022', '--esModuleInterop', '--skipLibCheck'], {cwd: path.resolve(__dirname, '..'), encoding: 'utf8'});
assert.equal(built.status, 0, built.stdout + built.stderr);
const dom = new JSDOM('<body><div id="root"></div></body>', {url: 'http://localhost', pretendToBeVisual: true});
Object.assign(global, {window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true});
Object.defineProperty(global, 'navigator', {value: dom.window.navigator, configurable: true});
const React = require('react');
const {createRoot} = require('react-dom/client');
const {RecipeWorkspace} = require(path.join(compiled, 'recipe-workspace.js'));
const {RecipeTrials} = require(path.join(compiled, 'recipe-trials.js'));
const recipe = {id:'ugc', name:'UGC', version:1, intent:'A readable demonstration', references:['Approved product views'], planning:['Explain the demonstration'], decision_requirements:['Explain why the framing serves the beat.'], roles:[{id:'demo',title:'Demonstration',purpose:'Show the feature',quality:['Product matches'],sound:'Tactile foley',repair:'Simplify the interaction',direction:{camera:{move:'Locked'},lighting:{technique:'Window'}}}], image_checks:['Product matches'], video_checks:['Action is clear'], final_checks:['Opening is paid off'], source_rules:[{id:'identity',section:'Lock references and state',teaching:'Use canonical references',correction:'Do not invent upload slots',provenance:'review_derived'}], stages:{brief:['State the viewer promise'],final_review:['Inspect the actual final edit']}, examples:[1,2,3].map(n=>({id:'ugc-'+n,title:'Example '+n,image:'/recipe-examples/ugc-'+n+'.png',available:true,prompt:'Exact generated prompt '+n,why:'Window light keeps the face readable.'}))};

test('recipe browsing reveals real examples and source rules; activation is explicit and revision checked', async()=>{
 const calls=[]; const created=[];
 global.fetch=async(_url,options)=>{const body=JSON.parse(options.body);calls.push(body);return {ok:true,json:async()=>({recipes:[recipe],coverage:{review_status:'Supplied review imported'}})};};
 const root=createRoot(document.getElementById('root'));
 await React.act(async()=>root.render(React.createElement(RecipeWorkspace,{project:{id:'p1',name:'Cup',revision:7,template_id:'ugc',production:{recipe:{id:'',version:0}}},busy:false,save:async fn=>fn(),onNew:id=>created.push(id)})));
 assert.equal(document.querySelectorAll('.cv-recipe-example img').length,3);
 assert.match(document.body.textContent,/Illustrative AI stills/);
 assert.match(document.body.textContent,/not video validation/);
 assert.equal(calls.filter(c=>c.operation==='activate_recipe').length,0);
 const click=async text=>{const b=[...document.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')===text || b.textContent.trim()===text);assert.ok(b,text);await React.act(async()=>b.click());};
 await click('Inspect Example 2');
 assert.match(document.body.textContent,/Exact generated prompt 2/);
 await click('Close example');
 await click('Course rules');
 assert.match(document.body.textContent,/Lock references and state/);
 assert.match(document.body.textContent,/Do not invent upload slots/);
 await click('Use for new project'); assert.deepEqual(created,['ugc']);
 await click('Activate for Cup');
 assert.deepEqual(calls.at(-1),{operation:'activate_recipe',arguments:{project_id:'p1',expected_revision:7},actor:'user'});
 await React.act(()=>root.unmount());
});

test('detail tabs support roving focus and link the active panel', async()=>{
 global.fetch=async()=>({ok:true,json:async()=>({recipes:[recipe],coverage:{review_status:'Partial page verification'}})});
 const root=createRoot(document.getElementById('root'));
 await React.act(async()=>root.render(React.createElement(RecipeWorkspace,{project:null,busy:false,save:async fn=>fn(),onNew:()=>{}})));
 const tabs=[...document.querySelectorAll('[role=tab]')];
 assert.deepEqual(tabs.map(t=>t.tabIndex),[0,-1,-1,-1]);
 tabs[0].focus();
 await React.act(async()=>tabs[0].dispatchEvent(new window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})));
 assert.equal(document.activeElement,tabs[1]);
 assert.equal(tabs[1].getAttribute('aria-selected'),'true');
 const panel=document.querySelector('[role=tabpanel]');
 assert.equal(panel.getAttribute('aria-labelledby'),tabs[1].id);
 assert.equal(tabs[1].getAttribute('aria-controls'),panel.id);
 await React.act(async()=>tabs[1].dispatchEvent(new window.KeyboardEvent('keydown',{key:'End',bubbles:true})));
 assert.equal(document.activeElement,tabs[3]);
 await React.act(async()=>tabs[3].dispatchEvent(new window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})));
 assert.equal(document.activeElement,tabs[0]);
 await React.act(()=>root.unmount());
});

test('examples contain keyboard focus, lock background scrolling and restore the opener', async()=>{
 global.fetch=async()=>({ok:true,json:async()=>({recipes:[recipe],coverage:{review_status:'Partial page verification'}})});
 const root=createRoot(document.getElementById('root'));
 await React.act(async()=>root.render(React.createElement(RecipeWorkspace,{project:null,busy:false,save:async fn=>fn(),onNew:()=>{}})));
 const opener=document.querySelector('.cv-recipe-example');opener.focus();
 await React.act(async()=>opener.click());
 const dialog=document.querySelector('[role=dialog]');
 assert.equal(document.body.style.overflow,'hidden');
 assert.ok(document.querySelector('[inert]'));
 const close=dialog.querySelector('button'),summary=dialog.querySelector('summary');
 assert.equal(document.activeElement,close);
 await React.act(async()=>close.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true})));
 assert.equal(document.activeElement,summary);
 await React.act(async()=>summary.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true})));
 assert.equal(document.querySelector('[role=dialog]'),null);
 assert.equal(document.activeElement,opener);
 assert.equal(document.body.style.overflow,'');
 await React.act(()=>root.unmount());
});

test('course citations distinguish page-backed principles from studio corrections', async()=>{
 const citation={source_id:'guide',title:'Short Film Guide',page:13,lesson_url:'https://example.com/classroom'};
 const cited={...recipe,source_rules:[{...recipe.source_rules[0],grounding:'original_pages_verified',citations:[citation],correction_citations:[{...citation,page:14}]}]};
 global.fetch=async()=>({ok:true,json:async()=>({recipes:[cited],coverage:{review_status:'Partial page verification',page_numbering:'One-based PDF file pages',verified_sources:[{source_id:'guide'}]}})});
 const root=createRoot(document.getElementById('root'));
 await React.act(async()=>root.render(React.createElement(RecipeWorkspace,{project:null,busy:false,save:async fn=>fn(),onNew:()=>{}})));
 await React.act(async()=>[...document.querySelectorAll('[role=tab]')].find(t=>t.textContent==='Course rules').click());
 const links=[...document.querySelectorAll('.cv-source-citations a')];
 assert.equal(links.length,2);
 assert.equal(links[0].href,citation.lesson_url);
 assert.match(links[0].textContent,/Short Film Guide.*13/);
 assert.match(links[1].textContent,/14/);
 assert.match(document.body.textContent,/Studio correction/);
 assert.match(document.body.textContent,/lesson links open the classroom/i);
 await React.act(()=>root.unmount());
});

test('trial assessments preserve conflicting drafts and failed submissions', async()=>{
 const calls=[];
 const draft={idea:'Preserved idea',note:'Watched the whole export',defects:'',watched:true,criteria:{'Opening is paid off':true}};
 const storageKey='frame-draft:recipe-trial:p1';
 window.sessionStorage.setItem(storageKey,JSON.stringify({draft,base:{},revision:7}));
 const project={id:'p1',revision:8,documents:{final_review:{export_asset_id:'final'}},assets:[{id:'final',kind:'final_video',stale:false}]};
 global.fetch=async(_url,options)=>{const body=JSON.parse(options.body);calls.push(body);if(body.operation==='record_recipe_trial')return {ok:false,json:async()=>({error:'Revision changed'})};return {ok:true,json:async()=>({revision:8,final_checks:['Opening is paid off'],scope:'Actual final edits only',trials:[]})};};
 const root=createRoot(document.getElementById('root'));
 let error;
 await React.act(async()=>root.render(React.createElement(RecipeTrials,{project,busy:false,save:async fn=>{try{await fn();}catch(e){error=e;}}})));
 assert.match(document.body.textContent,/Your draft is preserved/);
 const submit=[...document.querySelectorAll('button')].find(b=>b.textContent==='Record human assessment');
 assert.equal(submit.disabled,true);
 assert.equal(document.querySelector('input[maxlength="1000"]').value,draft.idea);
 await React.act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Rebase my draft').click());
 assert.equal(submit.disabled,false);
 await React.act(async()=>submit.click());
 assert.ok(error);
 const request=calls.find(c=>c.operation==='record_recipe_trial');
 assert.equal(request.arguments.expected_revision,8);
 assert.equal(request.arguments.assessment.asset_id,'final');
 assert.equal(JSON.parse(window.sessionStorage.getItem(storageKey)).draft.idea,draft.idea);
 await React.act(()=>root.unmount());
 window.sessionStorage.removeItem(storageKey);
});

test('illustrations and stale exports cannot be recorded as final-video trials', async()=>{
 global.fetch=async()=>({ok:true,json:async()=>({revision:1,final_checks:['Opening is paid off'],scope:'Actual final edits only',trials:[]})});
 const root=createRoot(document.getElementById('root'));
 for(const asset of [{id:'media',kind:'image',stale:false},{id:'media',kind:'final_video',stale:true}]){
  await React.act(async()=>root.render(React.createElement(RecipeTrials,{project:{id:'p-no-final',revision:1,documents:{final_review:{export_asset_id:'media'}},assets:[asset]},busy:false,save:async fn=>fn()})));
  assert.match(document.body.textContent,/No reviewed final productions recorded/);
  assert.match(document.body.textContent,/Selected clips and illustrative stills do not qualify/);
  assert.equal(document.querySelector('input'),null);
 }
 await React.act(()=>root.unmount());
});
