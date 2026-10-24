'use strict';
const path = require('node:path');
const fs = require('node:fs');
const net = require('node:net');
const http = require('node:http');
const { spawn } = require('node:child_process');
const { setTimeout: delay } = require('node:timers/promises');

function clearWebRouteCache(resources) {
  const root=path.resolve(resources);
  const target=path.resolve(root,'web','.next','server','route-cache');
  if(path.relative(root,target)!==path.join('web','.next','server','route-cache'))throw new Error('Invalid packaged route-cache path');
  let current=root;
  for(const part of ['web','.next','server','route-cache']) {
    current=path.join(current,part);
    if(!fs.existsSync(current))return;
    if(fs.lstatSync(current).isSymbolicLink())throw new Error('Refusing to clear a linked packaged route cache');
  }
  // Generated route HTML can survive an in-place NSIS upgrade and mask new bundles.
  // The fixed, checked target contains disposable Next cache, never project data.
  fs.rmSync(target,{recursive:true,force:true});
}

function buildLaunchPlan({ resources, dataDir, executable, backendPort, frontendPort, instanceId, env = process.env }) {
  const inherited = { ...env };
  // Windows treats environment keys case-insensitively; avoid duplicate Path/PATH.
  const pathKey = Object.keys(inherited).find((key) => key.toLowerCase() === 'path');
  const oldPath = pathKey ? inherited[pathKey] : '';
  if (pathKey) delete inherited[pathKey];
  const common = { ...inherited, PATH: path.join(resources, 'bin') + path.delimiter + oldPath, STUDIO_DATA_DIR: dataDir, STUDIO_RESOURCE_ROOT: path.join(resources, 'studio'), STUDIO_DESKTOP_INSTANCE: instanceId };
  const apiUrl = `http://127.0.0.1:${backendPort}`;
  return {
    apiUrl,
    frontendUrl: `http://127.0.0.1:${frontendPort}/studio`,
    backend: { command: path.join(resources, 'backend', 'FrameStudioService.exe'), args: ['serve', '--host', '127.0.0.1', '--port', String(backendPort), '--data-dir', dataDir], options: { cwd: path.join(resources, 'backend'), windowsHide: true, env: common, stdio: ['ignore', 'pipe', 'pipe'] } },
    frontend: { command: executable, args: [path.join(resources, 'web', 'server.js')], options: { cwd: path.join(resources, 'web'), windowsHide: true, env: { ...common, ELECTRON_RUN_AS_NODE: '1', HOSTNAME: '127.0.0.1', PORT: String(frontendPort), STUDIO_API_URL: apiUrl, NODE_ENV: 'production' }, stdio: ['ignore', 'pipe', 'pipe'] } },
  };
}

async function getFreePort() {
  const port = await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const value = server.address().port;
      server.close((error) => error ? reject(error) : resolve(value));
    });
  });
  return [3000, 8010].includes(port) ? getFreePort() : port;
}

function request(url, json) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, { timeout: 1500 }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { body += chunk; if (body.length > 1024 * 1024) req.destroy(new Error('Health response too large')); });
      response.on('error', reject);
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error(`HTTP ${response.statusCode}`));
        try { resolve(json ? JSON.parse(body) : { status: 'ok' }); } catch (error) { reject(error); }
      });
    });
    req.once('timeout', () => req.destroy(new Error('Health request timed out')));
    req.once('error', reject);
  });
}

async function waitForHealth(url, { instanceId, child, timeoutMs = 60000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    if (child && (child.exitCode !== null || child.signalCode !== null)) throw new Error(`Service exited before startup (code ${child.exitCode}, signal ${child.signalCode}). Check the desktop log.`);
    try {
      const result = await request(url, Boolean(instanceId));
      if (instanceId && result.instance_id !== instanceId) throw Object.assign(new Error('Service instance identity mismatch. A different process may have taken the startup port.'), { identityMismatch: true });
      return result;
    } catch (error) {
      if (error.identityMismatch) throw error;
      lastError = error;
    }
    await delay(150);
  }
  throw new Error(`Service startup timed out at ${url}: ${lastError?.message || 'no response'}. Check the desktop log and restart Orchestra.`);
}

async function cleanupChildren(children) {
  await Promise.all(children.map(async (child) => {
    if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
    const exited = new Promise((resolve) => { child.once('exit', resolve); child.once('error', resolve); });
    if (process.platform === 'win32') {
      // Only PIDs created by this app are passed here. /T includes ffmpeg workers.
      const terminate = (force) => new Promise((resolve) => {
        const args = ['/PID', String(child.pid), '/T'];
        if (force) args.push('/F');
        const terminator = spawn('taskkill.exe', args, { windowsHide: true, stdio: 'ignore' });
        terminator.once('error', () => { child.kill(); resolve(1); });
        terminator.once('exit', resolve);
      });
      // Request a normal tree shutdown first; headless Windows processes may
      // require forced termination because they have no message loop to close.
      const result = await terminate(false);
      if (result !== 0 && child.exitCode === null && child.signalCode === null) await terminate(true);
    } else {
      child.kill('SIGTERM');
    }
    await Promise.race([exited, delay(2500, undefined, { ref: false })]);
    if (child.exitCode === null && child.signalCode === null) {
      child.kill('SIGKILL');
      await Promise.race([exited, delay(1000, undefined, { ref: false })]);
    }
  }));
}

function isLocalNavigation(url, origin) {
  try { const target = new URL(url); return target.origin === new URL(origin).origin && !target.username && !target.password; } catch { return false; }
}

function isSafeExternal(url) {
  try { const target = new URL(url); return target.protocol === 'https:' && Boolean(target.hostname) && !target.username && !target.password; } catch { return false; }
}

module.exports = { clearWebRouteCache, buildLaunchPlan, getFreePort, waitForHealth, cleanupChildren, isLocalNavigation, isSafeExternal };
