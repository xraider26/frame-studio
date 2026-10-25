const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const path = require('node:path');
const runtime = require('../runtime.cjs');

test('physical root and discovery publication agree and cleanup only owns its instance', (t) => {
  const fs=require('node:fs'),os=require('node:os');
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'orchestra-root-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const resolved=runtime.resolveWritableRoot(root);
  assert.equal(resolved,fs.realpathSync(root));
  assert.deepEqual(fs.readdirSync(root),[]);
  const file=path.join(root,'desktop-runtime.json');
  runtime.publishRuntime(file,{api_url:'http://127.0.0.1:12345',instance_id:'mine',service_pid:42,data_root:resolved});
  assert.equal(JSON.parse(fs.readFileSync(file)).ready,true);
  runtime.removeOwnedRuntime(file,'other'); assert.equal(fs.existsSync(file),true);
  runtime.removeOwnedRuntime(file,'mine'); assert.equal(fs.existsSync(file),false);
  assert.match(runtime.serviceExitMessage('Studio service',1,null,true),/after startup/);
  assert.match(runtime.serviceExitMessage('Studio service',1,null,false),/during startup/);
});

test('redirected probe chooses physical root without abandoning existing logical state', (t) => {
  const fs=require('node:fs'),os=require('node:os');
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'orchestra-redirect-'));
  t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
  const logical=path.join(base,'logical'),physical=path.join(base,'physical');
  fs.mkdirSync(logical);fs.mkdirSync(physical);
  const io={...fs,realpathSync:(value)=>path.dirname(value)===logical&&path.basename(value).startsWith('.orchestra-probe-')?path.join(physical,path.basename(value)):fs.realpathSync(value)};
  assert.equal(runtime.resolveWritableRoot(logical,io),fs.realpathSync(physical));
  fs.writeFileSync(path.join(logical,'workflow.db'),'preserve');
  assert.throws(()=>runtime.resolveWritableRoot(logical,io),/competing state/);
  assert.equal(fs.readFileSync(path.join(logical,'workflow.db'),'utf8'),'preserve');
  assert.equal(fs.existsSync(path.join(physical,'workflow.db')),false);
});

test('startup removes only disposable Next route cache left by an earlier install', (t) => {
 const fs=require('node:fs'),os=require('node:os');
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'orchestra-upgrade-'));
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const resources=path.join(root,'resources'),cache=path.join(resources,'web','.next','server','route-cache');
 fs.mkdirSync(cache,{recursive:true});fs.writeFileSync(path.join(cache,'studio.html'),'old Frame Studio');
 fs.writeFileSync(path.join(resources,'web','.next','server','studio.html'),'new Orchestra');
 const data=path.join(root,'studio_data');fs.mkdirSync(data);fs.writeFileSync(path.join(data,'workflow.db'),'existing projects');
 runtime.clearWebRouteCache(resources);
 assert.equal(fs.existsSync(cache),false);
 assert.equal(fs.readFileSync(path.join(resources,'web','.next','server','studio.html'),'utf8'),'new Orchestra');
 assert.equal(fs.readFileSync(path.join(data,'workflow.db'),'utf8'),'existing projects');
 runtime.clearWebRouteCache(resources);
});

test('packaged launch uses bundled resources and isolated writable data', () => {
  const plan = runtime.buildLaunchPlan({ resources: path.resolve('fixture resources'), dataDir: path.resolve('user data'), executable: process.execPath, backendPort: 49120, frontendPort: 49121, instanceId: 'launch-identity', env: { PATH: 'existing-path' } });
  assert.equal(plan.backend.command, path.resolve('fixture resources/backend/FrameStudioService.exe'));
  assert.deepEqual(plan.backend.args, ['serve', '--host', '127.0.0.1', '--port', '49120', '--data-dir', path.resolve('user data')]);
  assert.equal(plan.backend.options.env.STUDIO_RESOURCE_ROOT, path.resolve('fixture resources/studio'));
  assert.equal(plan.backend.options.env.STUDIO_DESKTOP_INSTANCE, 'launch-identity');
  assert.ok(plan.backend.options.env.PATH.startsWith(path.resolve('fixture resources/bin') + path.delimiter));
  assert.equal(plan.backend.options.windowsHide, true);
  assert.deepEqual(plan.frontend.args, [path.resolve('fixture resources/web/server.js')]);
  assert.equal(plan.frontend.options.env.ELECTRON_RUN_AS_NODE, '1');
  assert.equal(plan.frontend.options.env.STUDIO_API_URL, 'http://127.0.0.1:49120');
  assert.equal(plan.frontendUrl, 'http://127.0.0.1:49121/studio');
  assert.equal(plan.frontend.options.env.HOSTNAME, '127.0.0.1');
  assert.equal(plan.frontend.options.windowsHide, true);
});

test('health rejects another running instance rather than adopting it', async (t) => {
  const server = http.createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ status: 'ok', instance_id: 'someone-else' })); });
  server.listen(0, '127.0.0.1'); await once(server, 'listening'); t.after(() => server.close());
  await assert.rejects(runtime.waitForHealth(`http://127.0.0.1:${server.address().port}/health`, { instanceId: 'mine', timeoutMs: 500 }), /identity|instance/i);
});

test('health accepts the matching bundled service and fails promptly on child exit', async (t) => {
  const server = http.createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ status: 'ok', instance_id: 'mine' })); });
  server.listen(0, '127.0.0.1'); await once(server, 'listening'); t.after(() => server.close());
  const result = await runtime.waitForHealth(`http://127.0.0.1:${server.address().port}/health`, { instanceId: 'mine', timeoutMs: 500 });
  assert.equal(result.instance_id, 'mine');
  await assert.rejects(runtime.waitForHealth('http://127.0.0.1:1/health', { child: { exitCode: 3, signalCode: null }, timeoutMs: 500 }), /exited.*3/i);
});

test('ports are loopback ephemeral ports and avoid development ports', async () => {
  const port = await runtime.getFreePort();
  assert.ok(port > 0); assert.notEqual(port, 3000); assert.notEqual(port, 8010);
});

test('window navigation stays on its local origin and external links require HTTPS', () => {
  const origin = 'http://127.0.0.1:49121';
  assert.equal(runtime.isLocalNavigation(origin + '/projects?q=1', origin), true);
  for (const url of ['http://127.0.0.1:49122', 'https://example.com', 'javascript:alert(1)', origin + '@example.com']) assert.equal(runtime.isLocalNavigation(url, origin), false);
  assert.equal(runtime.isSafeExternal('https://example.com/docs'), true);
  for (const url of ['file:///C:/secret', 'http://example.com', 'javascript:alert(1)', 'https://name:password@example.com']) assert.equal(runtime.isSafeExternal(url), false);
});

test('cleanup terminates owned children and leaves unrelated processes alive', async (t) => {
  const owned = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { windowsHide: true });
  const unrelated = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { windowsHide: true });
  t.after(() => { if (owned.exitCode === null && !owned.signalCode) owned.kill(); unrelated.kill(); });
  await Promise.all([once(owned, 'spawn'), once(unrelated, 'spawn')]);
  await runtime.cleanupChildren([owned]);
  assert.ok(owned.exitCode !== null || owned.signalCode !== null);
  assert.equal(unrelated.exitCode, null); assert.equal(unrelated.signalCode, null);
  await runtime.cleanupChildren([owned]);
});
