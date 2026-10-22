/* Reproducible, allowlisted Windows payload. Run under Node >=22.12. */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const buildRoot=path.join(__dirname,'build');

function isPrivate(relative){
 const parts=relative.replaceAll('\\','/').split('/');
 return parts.some(p=>['studio_data','media','inbox','course_sources','.git','.venv','__pycache__'].includes(p)||/^\.env(?:\.|$)/.test(p)||/\.(?:token|key|db|sqlite|sqlite3)(?:-|$)/i.test(p)||['connections.json','desktop-runtime.json'].includes(p));
}
function resetBuildDirectory(target,allowedRoot=buildRoot){
 const resolved=path.resolve(target),allowed=path.resolve(allowedRoot),relative=path.relative(allowed,resolved);
 if(!relative||relative.startsWith('..')||path.isAbsolute(relative))throw Error('Refusing cleanup outside an owned build subdirectory');
 fs.rmSync(resolved,{recursive:true,force:true});fs.mkdirSync(resolved,{recursive:true});
}
function copyTree(source,target){
 fs.cpSync(source,target,{recursive:true,dereference:true,filter:item=>!isPrivate(path.relative(source,item))});
}
function assertResources(stage){
 for(const relative of ['backend/FrameStudioService.exe','web/server.js','web/.next/BUILD_ID','web/public/cinematography/manifest.json','studio/docs/sources/verified-course-lessons.json','studio/frontend/public/recipe-examples/manifest.json','bin/ffmpeg.exe','bin/ffprobe.exe']){
  if(!fs.existsSync(path.join(stage,relative)))throw Error(`Missing packaged resource: ${relative}`);
 }
}
function run(file,args,cwd=root){
 const result=spawnSync(file,args,{cwd,stdio:'inherit',windowsHide:true});
 if(result.error)throw result.error;if(result.status!==0)throw Error(`${path.basename(file)} failed (${result.status})`);
}
function executable(name){
 if(process.env[`FRAME_STUDIO_${name.toUpperCase()}`])return process.env[`FRAME_STUDIO_${name.toUpperCase()}`];
 const result=spawnSync('where.exe',[`${name}.exe`],{encoding:'utf8',windowsHide:true});
 if(result.status!==0)throw Error(`${name} is required on the build machine`);
 return fs.realpathSync(result.stdout.trim().split(/\r?\n/)[0]);
}
async function main(){
 if(process.platform!=='win32')throw Error('Build this Windows installer on Windows');
 const [major,minor]=process.versions.node.split('.').map(Number);
 if(major<22||(major===22&&minor<12))throw Error('Node >=22.12 is required for desktop packaging');
 const args=new Set(process.argv.slice(2)),python=process.env.FRAME_STUDIO_PYTHON||path.join(root,'backend','.venv','Scripts','python.exe');
 fs.mkdirSync(buildRoot,{recursive:true});
 if(!args.has('--skip-web'))run(process.execPath,[path.join(root,'frontend','node_modules','next','dist','bin','next'),'build'],path.join(root,'frontend'));
 if(!args.has('--skip-freeze')){
  run(python,['-m','PyInstaller','--noconfirm','--clean','--onedir','--name','FrameStudioService','--distpath',path.join(buildRoot,'frozen'),'--workpath',path.join(buildRoot,'pyinstaller'),'--specpath',path.join(buildRoot,'spec'),'--paths',path.join(root,'backend'),'--collect-submodules','uvicorn','--collect-submodules','mcp.server','--collect-submodules','mcp.shared','--collect-data','mcp',path.join(root,'backend','studio_desktop.py')]);
 }
 const resources=path.join(buildRoot,'resources');resetBuildDirectory(resources);
 copyTree(path.join(buildRoot,'frozen','FrameStudioService'),path.join(resources,'backend'));
 const standalone=path.join(root,'frontend','.next','standalone');
 if(!fs.existsSync(path.join(standalone,'server.js')))throw Error('Standalone Next server missing; inspect tracing root before staging');
 copyTree(standalone,path.join(resources,'web'));
 copyTree(path.join(root,'frontend','.next','static'),path.join(resources,'web','.next','static'));
 copyTree(path.join(root,'frontend','public'),path.join(resources,'web','public'));
 copyTree(path.join(root,'docs','sources'),path.join(resources,'studio','docs','sources'));
 for(const group of ['cinematography','recipe-examples'])copyTree(path.join(root,'frontend','public',group),path.join(resources,'studio','frontend','public',group));
 fs.mkdirSync(path.join(resources,'bin'),{recursive:true});
 for(const name of ['ffmpeg','ffprobe'])fs.copyFileSync(executable(name),path.join(resources,'bin',`${name}.exe`));
 const vendorRoot=path.dirname(path.dirname(executable('ffmpeg')));
 if(fs.existsSync(path.join(vendorRoot,'LICENSE')))copyTree(path.join(vendorRoot,'LICENSE'),path.join(resources,'bin','FFMPEG-LICENSE.txt'));
 if(fs.existsSync(path.join(vendorRoot,'README.txt')))copyTree(path.join(vendorRoot,'README.txt'),path.join(resources,'bin','FFMPEG-README.txt'));
 copyTree(path.join(__dirname,'THIRD-PARTY-NOTICES.md'),path.join(resources,'THIRD-PARTY-NOTICES.md'));
 assertResources(resources);
 const revision=spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',windowsHide:true}).stdout.trim();
 fs.writeFileSync(path.join(resources,'build-info.json'),JSON.stringify({version:require('./package.json').version,revision,built_at:new Date().toISOString(),node:process.versions.node},null,2));
 if(args.has('--stage-only')){console.log(`Payload staged: ${resources}`);return;}
 const {build,Platform,Arch}=require('electron-builder');
 await build({projectDir:__dirname,targets:Platform.WINDOWS.createTarget(['nsis'],Arch.x64),publish:'never'});
 const setup=path.join(__dirname,'dist',`Frame-Studio-Setup-${require('./package.json').version}.exe`);
 if(!fs.existsSync(setup))throw Error('Installer output missing');
 fs.writeFileSync(setup+'.sha256',`${crypto.createHash('sha256').update(fs.readFileSync(setup)).digest('hex')}  ${path.basename(setup)}\n`);
 console.log(`Installer ready: ${setup}`);
}
module.exports={isPrivate,copyTree,resetBuildDirectory,assertResources};
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
