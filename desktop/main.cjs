'use strict';
const { app, BrowserWindow, Menu, clipboard, dialog, shell, session } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawn } = require('node:child_process');
const { buildLaunchPlan, getFreePort, waitForHealth, cleanupChildren, isLocalNavigation, isSafeExternal } = require('./runtime.cjs');

app.setName('Frame Studio');

let window;
let log;
let logPath;
let dataDir;
let runtimeFile;
let stopping = false;
let failed = false;
let instanceId;
const children = [];
const smoke = process.env.FRAME_STUDIO_SMOKE === '1';

function writeLog(message) {
  log?.write(`[${new Date().toISOString()}] ${message}\n`);
}

function writeSmoke(report) {
  const target = process.env.FRAME_STUDIO_SMOKE_REPORT;
  if (!smoke || !target) return;
  fs.mkdirSync(path.dirname(path.resolve(target)), { recursive: true });
  fs.writeFileSync(path.resolve(target), JSON.stringify(report, null, 2));
}

function fail(error) {
  if (stopping || failed) return;
  failed = true;
  writeLog(error.stack || String(error));
  writeSmoke({ ok: false, error: error.message, dataDir, logPath, instance_id: instanceId });
  if (!smoke) dialog.showErrorBox('Frame Studio could not start', `${error.message}\n\nLogs: ${logPath || app.getPath('logs')}\n\nClose Frame Studio and try again. If the problem continues, include this log when requesting help.`);
  app.quit();
}

function startChild(name, spec) {
  if (stopping) throw new Error('Startup cancelled');
  const child = spawn(spec.command, spec.args, spec.options);
  children.push(child);
  child.stdout?.on('data', (chunk) => writeLog(`[${name}] ${chunk.toString().trimEnd()}`));
  child.stderr?.on('data', (chunk) => writeLog(`[${name}] ${chunk.toString().trimEnd()}`));
  child.once('error', (error) => fail(new Error(`${name} could not launch: ${error.message}`)));
  child.once('exit', (code, signal) => {
    writeLog(`${name} exited (code ${code}, signal ${signal})`);
    if (!stopping) fail(new Error(`${name} stopped unexpectedly (code ${code}, signal ${signal}). A startup port collision or missing bundled file may be responsible.`));
  });
  return child;
}

function makeMenu(resources) {
  const mcp = { mcpServers: { 'frame-studio': { command: path.join(resources, 'backend', 'FrameStudioService.exe'), args: ['mcp', '--data-dir', dataDir] } } };
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Frame Studio', submenu: [
      { label: 'Copy MCP configuration', click: () => clipboard.writeText(JSON.stringify(mcp, null, 2)) },
      { label: 'Open data folder', click: () => { void shell.openPath(dataDir); } },
      { label: 'Open desktop log', click: () => { void shell.openPath(logPath); } },
      { type: 'separator' },
      { label: 'About Frame Studio', click: () => { void dialog.showMessageBox(window, { type: 'info', title: 'Frame Studio', message: `Frame Studio ${app.getVersion()}`, detail: 'Create short videos locally. Your projects and credentials stay in your data folder.' }); } },
      { role: 'quit' },
    ] },
    { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
    { label: 'View', submenu: [{ label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => window?.webContents.reload() }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] },
  ]));
}

async function start() {
  const resources = process.resourcesPath;
  dataDir = path.resolve(process.env.FRAME_STUDIO_DATA_DIR || path.join(app.getPath('userData'), 'studio_data'));
  fs.mkdirSync(dataDir, { recursive: true });
  const logsDir = path.join(dataDir, 'logs');
  fs.mkdirSync(logsDir, { recursive: true });
  logPath = path.join(logsDir, 'desktop.log');
  // Keep the previous launch for diagnostics without unbounded log growth.
  if (fs.existsSync(logPath) && fs.statSync(logPath).size > 5 * 1024 * 1024) {
    fs.rmSync(logPath + '.previous', { force: true });
    fs.renameSync(logPath, logPath + '.previous');
  }
  log = fs.createWriteStream(logPath, { flags: 'a' });
  log.on('error', (error) => { console.error('Desktop log error:', error.message); });
  instanceId = randomUUID();
  runtimeFile = path.join(dataDir, 'desktop-runtime.json');
  writeLog(`Frame Studio ${app.getVersion()} starting; instance ${instanceId}`);
  const loadingFile = path.join(__dirname, 'loading.html');
  window = new BrowserWindow({ width: 1440, height: 960, minWidth: 1024, minHeight: 720, show: false, backgroundColor: '#0c1017', title: 'Frame Studio', webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true, allowRunningInsecureContent: false } });
  window.once('ready-to-show', () => { if (!smoke) window?.show(); });
  window.on('closed', () => { window = null; });
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isSafeExternal(url)) void shell.openExternal(url).catch((error) => writeLog(`External link failed: ${error.message}`));
    return { action: 'deny' };
  });
  window.webContents.on('will-attach-webview', (event) => event.preventDefault());
  let origin;
  window.webContents.on('will-navigate', (event, url) => {
    if (!origin || !isLocalNavigation(url, origin)) event.preventDefault();
  });
  window.webContents.on('will-redirect', (event, url) => {
    if (!origin || !isLocalNavigation(url, origin)) event.preventDefault();
  });
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  await window.loadFile(loadingFile);
  if (stopping) return;
  for (const relative of ['backend/FrameStudioService.exe', 'web/server.js', 'bin/ffmpeg.exe', 'bin/ffprobe.exe']) {
    if (!fs.existsSync(path.join(resources, relative))) throw new Error(`A required bundled file is missing: ${relative}. Reinstall Frame Studio from the Windows installer.`);
  }
  const backendPort = await getFreePort();
  let frontendPort = await getFreePort();
  while (frontendPort === backendPort) frontendPort = await getFreePort();
  const plan = buildLaunchPlan({ resources, dataDir, executable: process.execPath, backendPort, frontendPort, instanceId });
  origin = plan.frontendUrl;
  // The app renders only bundled local content, including local backend media.
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (details, callback) => {
    callback({ cancel: !isLocalNavigation(details.url, plan.frontendUrl) && !isLocalNavigation(details.url, plan.apiUrl) });
  });
  makeMenu(resources);
  const backend = startChild('Video service', plan.backend);
  await waitForHealth(plan.apiUrl + '/health', { instanceId, child: backend, timeoutMs: 90000 });
  if (stopping) return;
  fs.writeFileSync(runtimeFile + '.tmp', JSON.stringify({ api_url: plan.apiUrl, instance_id: instanceId }, null, 2));
  fs.renameSync(runtimeFile + '.tmp', runtimeFile);
  const frontend = startChild('Studio interface', plan.frontend);
  await waitForHealth(plan.frontendUrl, { child: frontend, timeoutMs: 90000 });
  if (stopping || !window) return;
  await window.loadURL(plan.frontendUrl);
  if (stopping || !window) return;
  if (!smoke) window.show();
  writeLog(`Ready: interface ${plan.frontendUrl}; service ${plan.apiUrl}`);
  writeSmoke({ ok: true, browser_loaded: true, dataDir, frontendURL: plan.frontendUrl, backendURL: plan.apiUrl, instance_id: instanceId, logPath, resourcesPath: resources, backendPid: backend.pid, frontendPid: frontend.pid });
  if (smoke) {
    const configured = Number(process.env.FRAME_STUDIO_SMOKE_MS || 30000);
    const duration = Number.isFinite(configured) && configured >= 0 ? configured : 30000;
    setTimeout(() => app.quit(), duration).unref();
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); } });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', (event) => {
    event.preventDefault();
    if (stopping) return;
    stopping = true;
    void (async () => {
      await cleanupChildren(children);
      try {
        if (runtimeFile && fs.existsSync(runtimeFile) && JSON.parse(fs.readFileSync(runtimeFile, 'utf8')).instance_id === instanceId) fs.rmSync(runtimeFile);
      } catch (error) { writeLog(`Runtime file cleanup: ${error.message}`); }
      writeLog('Frame Studio stopped.');
      if (log) await new Promise((resolve) => log.end(resolve));
      app.exit(failed ? 1 : 0);
    })().catch((error) => { console.error(error); app.exit(1); });
  });
  app.whenReady().then(start).catch(fail);
}
