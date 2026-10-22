const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { existsSync } = require('node:fs');
const { spawnSync } = require('node:child_process');
const { JSDOM } = require('jsdom');
const source = path.resolve(__dirname, '../src/app/studio/cinematography-library.tsx');
const compiled = path.resolve(__dirname, '../.studio-test/cinematography');
if (existsSync(source)) {
  const result = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'), source, '--outDir', compiled, '--jsx', 'react-jsx', '--module', 'commonjs', '--target', 'ES2022', '--esModuleInterop', '--skipLibCheck'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
}
const dom = new JSDOM('<body><div id="root"></div></body>', {url:'http://localhost', pretendToBeVisual:true});
Object.assign(global, { window:dom.window, document:dom.window.document, HTMLElement:dom.window.HTMLElement, Node:dom.window.Node, IS_REACT_ACT_ENVIRONMENT:true });
Object.defineProperty(global, 'navigator', {value:dom.window.navigator, configurable:true});
const React = require('react');
const {createRoot} = require('react-dom/client');
const Library = existsSync(source) ? require(path.join(compiled, 'cinematography-library.js')).CinematographyLibrary : undefined;
const makeEntry = (id, name, category, apply, group='portrait-look') => ({id,name,category,apply,explanation:'A controlled portrait study.',use_when:'Character scenes',risk:'Check the highlights.',safer_alternative:'Use soft fill.',source:'Studio',source_note:'Studio adaptation',section:'Camera',provenance:'studio',visual:{kind:category,variant:id,sample:{image:`/examples/${id}.png`,prompt:'An actor by a window',caption:'Generated comparison still',comparison_group:group,kind:'generated_still'}}});
const entries = [makeEntry('film','Film cinema','camera',{camera:{body_look:'Film cinema'}}),makeEntry('digital','Digital cinema','camera',{camera:{body_look:'Digital cinema'}}),makeEntry('other','Other scene','camera',{camera:{body_look:'Other'}},'other-scene'),makeEntry('soft','Soft light','lighting',{lighting:{key:'Soft'}})];
const catalog = {entries,categories:['camera','lighting'],coverage:{status:'Studio reference',entry_count:4,limitations:'Generated examples',full_original_catalogues:false}};
function project(revision=7) { return {id:'p',revision,name:'My film',shots:[{id:'one',title:'Arrival',direction:{camera:{lens:'50mm'},lighting:{key:'Practical'},mood:'Quiet',technique_ids:['existing']}},{id:'two',title:'Departure',direction:{camera:{body_look:'Override'},technique_ids:[]}}],production:{defaults:{camera:{lens:'35mm'},lighting:{key:'Daylight'},mood:'Warm',technique_ids:['default-existing']},brief:{subject:'Actor'},bible:[]}}; }
async function mount(extra={}) {
  assert.equal(typeof Library,'function','Cinematography library must be implemented');
  const calls=[];
  global.fetch=async(_url,options)=>{calls.push(JSON.parse(options.body));return {ok:true,json:async()=>({revision:8})};};
  const root=createRoot(document.getElementById('root'));
  const props={catalog,project:project(),busy:false,save:async fn=>{await fn();},...extra};
  await React.act(()=>root.render(React.createElement(Library,props)));
  return {root,props,calls,close:async()=>React.act(()=>root.unmount())};
}
async function click(text) {const button=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text || b.getAttribute('aria-label')===text);assert.ok(button,`Button: ${text}`);await React.act(()=>button.click());}
async function select(label,value) {const input=document.querySelector(`[aria-label="${label}"]`);assert.ok(input,label);await React.act(()=>{input.value=value;input.dispatchEvent(new window.Event('change',{bubbles:true}));});}

test('browsing, searching and comparing never mutate project direction',async()=>{
 const m=await mount();
 await click('Digital cinema');
 await click('Compare looks');
 await select('Compare with','film');
 assert.equal(m.calls.length,0);
 assert.match(document.body.textContent,/same reference scene/i);
 assert.equal(document.querySelector('[aria-label="Compare with"] option[value="other"]'),null,'Different comparison groups must not imply a controlled comparison');
 assert.ok(document.querySelector('img[src="/examples/digital.png"]'));
 await m.close();
});

test('camera looks are the discoverable starting category regardless of catalogue order',async()=>{
 const m=await mount({catalog:{...catalog,entries:[entries[3],...entries.slice(0,3)]}});
 const category=[...document.querySelectorAll('button')].find(b=>b.textContent==='Camera looks');
 assert.equal(category.getAttribute('aria-pressed'),'true');
 assert.ok(document.querySelector('img[src="/examples/film.png"]'));
 await m.close();
});
test('shot application requires an explicit target and preserves unrelated direction and shots',async()=>{
 const m=await mount();
 const apply=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Apply to shot');
 assert.equal(apply.disabled,true);
 await select('Target shot','one');
 assert.match(document.body.textContent,/camera.body_look/);
 await click('Apply to shot');
 assert.equal(m.calls.length,1);
 const {operation,arguments:a}=m.calls[0];
 assert.equal(operation,'update_shots');assert.equal(a.expected_revision,7);
 assert.equal(a.shots[0].direction.camera.body_look,'Film cinema');
 assert.equal(a.shots[0].direction.camera.lens,'50mm');
 assert.equal(a.shots[0].direction.mood,'Quiet');
 assert.deepEqual(a.shots[0].direction.technique_ids,['existing','film']);
 assert.deepEqual(a.shots[1],project().shots[1]);
 await m.close();
});
test('project defaults merge one technique without rewriting shot overrides',async()=>{
 const m=await mount();await click('Apply as project defaults');
 const {operation,arguments:a}=m.calls[0];
 assert.equal(operation,'update_production');assert.equal(a.expected_revision,7);
 assert.equal(a.shots,undefined);
 assert.equal(a.production.defaults.camera.body_look,'Film cinema');
 assert.equal(a.production.defaults.camera.lens,'35mm');
 assert.equal(a.production.defaults.mood,'Warm');
 assert.deepEqual(a.production.defaults.technique_ids,['default-existing','film']);
 assert.deepEqual(a.production.brief,{subject:'Actor'});
 assert.match(document.body.textContent,/shot overrides/i);
 assert.match(document.body.textContent,/saved templates/i);
 await m.close();
});
test('new project revisions are used in the preview and command, never a stale snapshot',async()=>{
 const m=await mount();await select('Target shot','one');
 const fresh=project(11);fresh.shots[0].direction.camera.lens='85mm';
 await React.act(()=>m.root.render(React.createElement(Library,{...m.props,project:fresh})));
 assert.match(document.body.textContent,/revision 11/i);
 await click('Apply to shot');
 assert.equal(m.calls[0].arguments.expected_revision,11);
 assert.equal(m.calls[0].arguments.shots[0].direction.camera.lens,'85mm');
 await m.close();
});
test('switching projects clears the explicit shot target even if shot IDs overlap',async()=>{
 const m=await mount();await select('Target shot','one');
 const another={...project(12),id:'another-project',name:'Another film'};
 await React.act(()=>m.root.render(React.createElement(Library,{...m.props,project:another})));
 assert.equal(document.querySelector('[aria-label="Target shot"]').value,'');
 const apply=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Apply to shot');
 assert.equal(apply.disabled,true);
 assert.equal(m.calls.length,0);
 await m.close();
});
test('save failures remain visible and never claim application succeeded',async()=>{
 const m=await mount({save:async fn=>{try{await fn();}catch{ /* parent save boundary */ }}});
 global.fetch=async()=>({ok:false,json:async()=>({message:'Revision conflict. Refresh project.'})});
 await click('Apply as project defaults');
 assert.match(document.querySelector('[role="alert"]').textContent,/Revision conflict/);
 assert.doesNotMatch(document.querySelector('[role="status"]')?.textContent||'',/applied/i);
 await m.close();
});
test('movement scrubbing changes the projected scene without autoplay and distinguishes pan from dolly',async()=>{
 const movement=['dolly','pan','orbit','locked'].map(id=>({...makeEntry(id,id,'movement',{camera:{movement:id}}),visual:{kind:'movement',variant:id,motion:{id,duration_seconds:6,kind:'spatial_demonstration'}}}));
 const m=await mount({catalog:{...catalog,entries:movement,categories:['movement']}});
 const svg=document.querySelector('[aria-label="Camera view spatial demonstration"]');assert.ok(svg);
 const before=svg.innerHTML;
 const scrub=document.querySelector('[aria-label="Scrub camera demonstration"]');
 await React.act(()=>{Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(scrub,'4');scrub.dispatchEvent(new window.Event('input',{bubbles:true}));scrub.dispatchEvent(new window.Event('change',{bubbles:true}));});
 assert.notEqual(svg.innerHTML,before);
 assert.match(document.body.textContent,/spatial demonstration/i);
 assert.ok([...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Play'));
 await click('pan');assert.notEqual(document.querySelector('[aria-label="Camera view spatial demonstration"]').innerHTML,before);
 assert.equal(m.calls.length,0);
 await m.close();
});
test('reduced-motion preferences keep playback paused while scrubbing remains available',async()=>{
 window.matchMedia=()=>({matches:true,addEventListener(){},removeEventListener(){}});
 const movement={...makeEntry('orbit','Orbit','movement',{camera:{movement:'orbit'}}),visual:{kind:'movement',variant:'orbit',motion:{id:'orbit',duration_seconds:6,kind:'spatial_demonstration'}}};
 const m=await mount({catalog:{...catalog,entries:[movement],categories:['movement']}});
 const play=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Play');
 assert.equal(play.disabled,true);
 assert.equal(document.querySelector('[aria-label="Scrub camera demonstration"]').disabled,false);
 assert.match(document.body.textContent,/Reduced motion: use the scrubber/);
 await m.close();delete window.matchMedia;
});
test('an in-flight application disables both scopes and never sends a duplicate command',async()=>{
 const m=await mount();let finish;const requests=[];
 global.fetch=(_url,options)=>{requests.push(JSON.parse(options.body));return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({revision:8})});});};
 const button=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Apply as project defaults');
 await React.act(()=>{button.click();button.click();});
 assert.equal(button.disabled,true);
 assert.equal(requests.length,1);
 assert.match(document.querySelector('[role="status"]').textContent,/Saving/);
 await React.act(async()=>{finish();});
 assert.match(document.querySelector('[role="status"]').textContent,/applied to project defaults/);
 assert.equal(button.disabled,true,'Wait for the refreshed project revision before another apply');
 await m.close();
});
