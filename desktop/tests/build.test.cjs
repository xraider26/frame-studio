const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {isPrivate,copyTree,resetBuildDirectory,assertResources}=require('../build.cjs');

test('packaging excludes project data and credentials without excluding public source metadata',()=>{
 for(const name of ['studio_data/workflow.db','.env.local','backend/agent.token','media/a.mp4','course_sources/original.pdf','connections.json'])assert.equal(isPrivate(name),true,name);
 for(const name of ['docs/sources/verified-course-lessons.json','node_modules/token/index.js','cinematography/50mm.png'])assert.equal(isPrivate(name),false,name);
});
test('stage copying materializes files and excludes secrets recursively',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'frame stage '));
 try {const source=path.join(root,'src');fs.mkdirSync(source);fs.writeFileSync(path.join(source,'server.js'),'server');fs.writeFileSync(path.join(source,'.env'),'secret');fs.mkdirSync(path.join(source,'studio_data'));fs.writeFileSync(path.join(source,'studio_data','project.json'),'private');copyTree(source,path.join(root,'out'));assert.equal(fs.readFileSync(path.join(root,'out','server.js'),'utf8'),'server');assert.equal(fs.existsSync(path.join(root,'out','.env')),false);assert.equal(fs.existsSync(path.join(root,'out','studio_data')),false);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('build cleanup refuses root and paths outside its owned build folder',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'frame clean '));
 try{const build=path.join(root,'build');fs.mkdirSync(build);assert.throws(()=>resetBuildDirectory(root,build));assert.throws(()=>resetBuildDirectory(build,build));const stage=path.join(build,'resources');fs.mkdirSync(stage);fs.writeFileSync(path.join(stage,'old'),'old');resetBuildDirectory(stage,build);assert.equal(fs.existsSync(path.join(stage,'old')),false);assert.equal(fs.existsSync(root),true);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('incomplete bundled runtimes fail before producing an installer',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'frame verify '));try{assert.throws(()=>assertResources(root),/Missing packaged resource/);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
