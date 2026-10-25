/* Actual packaged binary check with isolated data and no Node/Python/FFmpeg on PATH. */
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');const {spawn,spawnSync}=require('node:child_process');const {setTimeout:delay}=require('node:timers/promises');
const root=path.resolve(__dirname,'..');
async function main(){
 const executable=path.resolve(process.argv[2]||path.join(__dirname,'dist','win-unpacked','Orchestra.exe'));
 const working=fs.mkdtempSync(path.join(root,'.superpowers','Frame desktop smoke '));
 let data=process.argv[3]?path.resolve(process.argv[3]):path.join(working,'Creator data');const reportFile=path.join(working,'report.json');
 const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>['SYSTEMROOT','WINDIR','TEMP','TMP','APPDATA','LOCALAPPDATA','USERPROFILE','COMSPEC','HOMEDRIVE','HOMEPATH'].includes(k.toUpperCase())));
 Object.assign(env,{PATH:path.join(process.env.SystemRoot,'System32'),FRAME_STUDIO_DATA_DIR:data,FRAME_STUDIO_SMOKE:'1',FRAME_STUDIO_SMOKE_MS:'30000',FRAME_STUDIO_SMOKE_REPORT:reportFile});
 const app=spawn(executable,[],{cwd:working,env,windowsHide:true,stdio:'ignore'});
 app.once('error',error=>{console.error(error);process.exitCode=1;});
 let exit;app.once('exit',code=>{exit=code;});
 const deadline=Date.now()+180000;
 while(!fs.existsSync(reportFile)&&Date.now()<deadline&&exit===undefined)await delay(250);
 assert.ok(fs.existsSync(reportFile),`No startup report. App exit ${exit}; inspect ${working}`);
 const report=JSON.parse(fs.readFileSync(reportFile,'utf8'));assert.equal(report.ok,true,JSON.stringify(report));assert.equal(new URL(report.frontendURL).pathname,'/studio');
 data=report.dataDir;
 const token=fs.readFileSync(path.join(data,'browser.token'),'utf8').trim();
 async function command(operation,arguments_={}){const r=await fetch(report.backendURL+'/studio/v1/command',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({operation,arguments:arguments_})});const body=await r.json();assert.equal(r.status,200,JSON.stringify(body));return body;}
 const caps=await command('studio_capabilities');assert.equal(caps.mcp_launch.desktop,true);assert.equal(path.resolve(caps.mcp_launch.command),path.resolve(report.resourcesPath,'backend','FrameStudioService.exe'));assert.equal(caps.mcp_launch.args.at(-1),data);
 const knowledge=await command('knowledge_catalog');assert.equal(knowledge.coverage.sample_count,26);const recipes=(await command('recipe_catalog')).recipes;assert.equal(recipes.length,16);assert.equal(recipes.filter(r=>r.output_type==='image').length,7);assert.ok(caps.execution_modes.includes('comfyui'));assert.ok(caps.image_profiles.some(p=>p.id==='qwen_image'));
 for(const entry of knowledge.entries.filter(e=>e.visual.sample)){const response=await fetch(new URL(entry.visual.sample.image,report.frontendURL),{method:'HEAD'});assert.equal(response.status,200,entry.id);}
 const page=await fetch(report.frontendURL);assert.equal(page.status,200);assert.match(await page.text(),/Orchestra/i);
 if(process.argv[3]&&!process.argv.includes('--new-data'))assert.ok((await command('list_projects')).some(p=>p.name==='Packaged verification fixture'),'Saved project was not recovered after restart');
 const project=await command('create_project',{name:'Packaged verification fixture',template_id:'ai-film',request_id:'desktop-smoke'});
 const clip=path.join(data,'inbox','synthetic-smoke.mp4');
 const ffmpeg=spawnSync(path.join(report.resourcesPath,'bin','ffmpeg.exe'),['-v','error','-y','-f','lavfi','-i','color=c=orange:s=160x90:d=1','-c:v','libx264','-pix_fmt','yuv420p',clip],{env,windowsHide:true,encoding:'utf8',timeout:15000});assert.equal(ffmpeg.status,0,ffmpeg.stderr);
 const imported=await command('import_reference',{project_id:project.id,expected_revision:project.revision,path:clip,name:'Synthetic test clip',kind:'video'});assert.ok(imported);
 // Claim/return a real synthetic PNG through the packaged service, without a
 // generator call or a creator style acceptance. This exercises physical roots.
 let still=await command('create_project',{name:'Packaged still fixture',template_id:'image-custom',output_type:'image',generation_setup:{version:1,image:{executor:'agent_builtin',tool_name:'Built-in image tool',profile:'general_image',model:null,model_version_status:'managed',connection_id:null,selection_source:'creator_statement',source_text:'Synthetic smoke fixture only'}}});
 still=await command('update_settings',{project_id:still.id,expected_revision:still.revision,settings:{creative_intake:{vision:'Synthetic orange fixture',art_style:'Flat color',purpose:'Packaged return check'}}});
 for(const step of ['brief','script'])still=await command('complete_step',{project_id:still.id,step,output:{text:'Synthetic test document'},expected_revision:still.revision});
 still=await command('update_shots',{project_id:still.id,shots:[{title:'Fixture',image_prompt:'Synthetic orange fixture'}],expected_revision:still.revision});
 const claim=await command('claim_generation',{project_id:still.id,request_id:'packaged-still',expected_revision:still.revision});assert.equal(claim.schema_version,3);assert.equal(claim.job.handoff,undefined);
 still=await command('get_project',{project_id:still.id});
 await command('record_generation_execution',{job_id:claim.job.id,expected_revision:still.revision,execution:{tool:'synthetic-local-fixture',prompt:claim.handoff.prompt,negative_prompt:claim.handoff.negative_prompt,references:claim.handoff.references,arguments:{fixture:true}}});
 const png=path.join(data,'inbox','synthetic-return.png');
 const made=spawnSync(path.join(report.resourcesPath,'bin','ffmpeg.exe'),['-v','error','-y','-f','lavfi','-i','color=c=orange:s=160x90','-frames:v','1',png],{env,windowsHide:true,encoding:'utf8',timeout:15000});assert.equal(made.status,0,made.stderr);
 const returned=await command('return_generation',{job_id:claim.job.id,output_path:png});assert.equal(returned.asset.kind,'image');
 assert.equal((await command('next_action',{project_id:still.id})).action,'record_quality');
 const python=process.env.FRAME_STUDIO_PYTHON||path.join(root,'backend','.venv','Scripts','python.exe');
 // Reproduce the failed boundary: the MCP client cannot see the legacy runtime
 // and sees a credential different from the service's in-memory credential.
 const runtimePath=path.join(data,'desktop-runtime.json'),agentPath=path.join(data,'agent.token');
 const runtimeRecord=fs.readFileSync(runtimePath),agentRecord=fs.readFileSync(agentPath);
 try {
  fs.unlinkSync(runtimePath);fs.writeFileSync(agentPath,'synthetic-shadow-credential');
  const mcp=spawnSync(python,[path.join(__dirname,'verify_mcp.py'),path.join(report.resourcesPath,'backend','FrameStudioService.exe'),data],{cwd:working,windowsHide:true,encoding:'utf8',timeout:65000});assert.equal(mcp.status,0,mcp.stderr);console.log(mcp.stdout.trim());
 } finally {fs.writeFileSync(runtimePath,runtimeRecord);fs.writeFileSync(agentPath,agentRecord);}
 // The second launch should focus the existing instance, not start two services.
 const second=spawnSync(executable,[],{cwd:working,env,windowsHide:true,encoding:'utf8',timeout:10000});assert.equal(second.status,0,second.stderr);
 while(exit===undefined&&Date.now()<deadline)await delay(250);
 assert.equal(exit,0,`Unexpected packaged app exit. ${report.logPath}`);assert.equal(fs.existsSync(path.join(data,'desktop-runtime.json')),false);assert.ok(fs.existsSync(path.join(data,'workflow.db')));
 for(const pid of [report.backendPid,report.frontendPid]){let alive=true;try{process.kill(pid,0);}catch{alive=false;}assert.equal(alive,false,`Owned service ${pid} survived app exit`);}
 fs.writeFileSync(path.join(working,'verification.json'),JSON.stringify({passed:true,project_id:project.id,executable,report,checks:['clean-PATH startup','installed MCP paths','26 still URLs','16 image/video recipes','Qwen and ComfyUI capabilities','bundled FFmpeg/FFprobe video import','schema3 claim and real PNG return','actual stdio MCP with missing legacy runtime and shadow credential','single instance','owned child shutdown','data retained']},null,2));
 console.log(`Packaged checks passed: ${working}`);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
