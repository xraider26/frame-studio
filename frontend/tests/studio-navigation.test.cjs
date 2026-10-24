const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const out=path.resolve(__dirname,'../.studio-test/navigation');
const built=spawnSync(process.execPath,[require.resolve('typescript/bin/tsc'),'src/app/studio/studio-navigation.ts','--outDir',out,'--module','commonjs','--target','ES2022','--skipLibCheck'],{cwd:path.resolve(__dirname,'..'),encoding:'utf8'});
assert.equal(built.status,0,built.stdout+built.stderr);
const {stageForView,nextActionTarget,templatesForOutput,templateForOutput}=require(path.join(out,'studio-navigation.js'));
test('continue opens the tool required by the saved action without completing or approving it',()=>{
 for(const [action,step,kind,want] of [
  ['ask_creator','brief','image',{view:'home'}],
  ['prepare_step','brief','video',{view:'workflow',step:'brief'}],
  ['prepare_step','script','image',{view:'workflow',step:'script'}],
  ['prepare_step','visual_direction','image',{view:'shots'}],
  ['generate','visual_direction','image',{view:'generator'}],
  ['write_prompt','visual_direction','image',{view:'shots'}],
  ['prepare_shots','script','video',{view:'shots'}],
  ['quality_attention','pilot','video',{view:'takes'}],
  ['record_quality','pilot','video',{view:'takes'}],
  ['await_approval','script','image',{view:'review',step:'script'}],
  ['resolve_preflight','pilot','video',{view:'shots'}],
  ['resolve_resources','pilot','video',{view:'production'}],
  ['prepare_step','final_review','video',{view:'workflow',step:'final_review'}],
  ['complete','final_review','image',{view:'delivery'}],
  ['complete','final_review','video',{view:'handoff'}],
 ]) assert.deepEqual(nextActionTarget({action,step,message:''},kind),want,`${action}/${step}`);
});
test('documents stay under their project stage and explicit approval review stays in Review',()=>{
 for(const [view,step,want] of [['workflow','brief','brief'],['workflow','script','plan'],['workflow','editor_handoff','export'],['review','brief','review'],['generator',undefined,'create'],['import',undefined,'create'],['delivery',undefined,'export'],['sequences',undefined,'plan'],['production',undefined,null],['queue',undefined,null]]) assert.equal(stageForView(view,step),want);
});
test('output switching filters templates by metadata and preserves valid choices',()=>{
 const templates=[{id:'legacy'},{id:'image-custom',output_type:'image'},{id:'portrait',output_type:'image'},{id:'ai-film',output_type:'video'}];
 assert.deepEqual(templatesForOutput(templates,'image').map(t=>t.id),['image-custom','portrait']);
 assert.deepEqual(templatesForOutput(templates,'video').map(t=>t.id),['legacy','ai-film']);
 assert.equal(templateForOutput(templates,'image','legacy'),'image-custom');
 assert.equal(templateForOutput(templates,'image','portrait'),'portrait');
 assert.equal(templateForOutput(templates,'video','portrait'),'ai-film');
});
