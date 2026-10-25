const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

// Exercise main's startup through the Electron boundary without starting services.
// Removing the explicit legacy userData path would strand installed users' data.
for (const {override,smoke} of [{},{override:'custom creator data'},{override:'isolated smoke data',smoke:true}]) {
  test(`Orchestra startup preserves ${override ? 'the existing data override' : 'installed Frame Studio data'}`, async (t) => {
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'orchestra brand '));
    t.after(() => fs.rmSync(profile, { recursive: true, force: true }));
    const legacy = path.join(profile, 'Frame Studio');
    const expected = override ? path.join(profile, override) : path.join(legacy, 'studio_data');
    fs.mkdirSync(expected, { recursive: true });
    fs.writeFileSync(path.join(expected, 'workflow.db'), 'existing projects');
    fs.writeFileSync(path.join(expected, 'connections.json'), 'existing connections');
    let name = 'frame-studio-desktop';
    let userData;
    let windowOptions;
    let start;
    const calls = [];
    const app = {
      setName(value) { name = value; },
      setPath(key, value) { assert.equal(key, 'userData'); assert.ok(fs.existsSync(value), 'Electron setPath requires an existing directory'); userData = value; calls.push('setPath'); },
      getPath(key) { calls.push(`getPath:${key}`); return key === 'appData' ? profile : userData || path.join(profile, name); },
      requestSingleInstanceLock() { return true; },
      on() {},
      whenReady() { return { then(fn) { start = fn; return { catch() {} }; } }; },
      getVersion() { return '0.2.0'; },
    };
    class BrowserWindow {
      constructor(options) { windowOptions = options; }
      once() {}
      on() {}
      webContents = { setWindowOpenHandler() {}, on() {} };
      loadFile() { return new Promise(() => {}); }
    }
    const electron = { app, BrowserWindow, session: { defaultSession: { setPermissionRequestHandler() {}, setPermissionCheckHandler() {} } } };
    const env = override ? { FRAME_STUDIO_DATA_DIR: expected } : {};
    if(smoke)env.FRAME_STUDIO_SMOKE='1';
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../main.cjs'), 'utf8'), {
      require(id) {
        if (id === 'electron') return electron;
        if (id === 'node:fs') return { ...fs, createWriteStream() { return { on() {}, write() {} }; } };
        if (id === './runtime.cjs') return require('../runtime.cjs');
        if (id === './mcp-config.cjs') return require('../mcp-config.cjs');
        return require(id);
      },
      __dirname: path.join(__dirname, '..'), process: { env, resourcesPath: profile }, console,
    });
    start();
    assert.equal(name, 'Orchestra');
    assert.equal(userData, smoke ? path.join(expected,'.electron-smoke') : legacy);
    if (!override) assert.ok(calls.indexOf('setPath') < calls.indexOf('getPath:userData'));
    assert.equal(windowOptions.title, 'Orchestra');
    assert.equal(fs.readFileSync(path.join(expected, 'workflow.db'), 'utf8'), 'existing projects');
    assert.equal(fs.readFileSync(path.join(expected, 'connections.json'), 'utf8'), 'existing connections');
    assert.equal(fs.existsSync(path.join(expected, 'logs')), true);
    assert.equal(fs.existsSync(path.join(profile, 'Orchestra')), false);
  });
}
