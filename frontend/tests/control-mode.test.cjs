const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { JSDOM } = require('jsdom');
const compiled = path.resolve(__dirname, '../.studio-test/modes');
const built = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'),
  'src/app/studio/creative-workspace.tsx', 'src/app/studio/production-workspace.tsx',
  'src/app/studio/generator-export.tsx', '--outDir', compiled, '--jsx', 'react-jsx',
  '--module', 'commonjs', '--target', 'ES2022', '--esModuleInterop', '--skipLibCheck'],
  { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' });
assert.equal(built.status, 0, built.stdout + built.stderr);
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost' });
Object.assign(global, { window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true });
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true });
const React = require('react');
const { createRoot } = require('react-dom/client');
const { CreativeWorkspace } = require(path.join(compiled, 'creative-workspace.js'));
const { GeneratorExport } = require(path.join(compiled, 'generator-export.js'));
const { ProductionWorkspace } = require(path.join(compiled, 'production-workspace.js'));
const fixture = spawnSync(path.resolve(__dirname, '../../backend/.venv/Scripts/python.exe'), ['-c',
  "import json,tempfile;from pathlib import Path;from studio.workflow import Studio;t=tempfile.TemporaryDirectory();r=Path(t.name);s=Studio(r/'db',r/'media',r/'inbox');p=s.create_project('Fixture','ai-film');print(json.dumps(s.get_project(p['id'])))"],
  { cwd: path.resolve(__dirname, '../../backend'), encoding: 'utf8' });
assert.equal(fixture.status, 0, fixture.stderr);
const project = JSON.parse(fixture.stdout);
const profiles = [{ id: 'custom', name: 'Custom', hint: 'Custom profile' }];
const generatorProject = { ...project, settings: { ...project.settings, video_generator: 'custom',
  image_generator: 'custom', custom_video_template: '{motion}', custom_image_template: '{subject}' } };
function props(p = project) { return { project: p, catalog: null, busy: false,
  inbox: 'test-inbox', save: async (fn) => fn(), videoProfiles: profiles, imageProfiles: profiles }; }
const mode = (name) => [...document.querySelectorAll('[role="radio"]')].find((b) => b.textContent === name);
const field = (label) => {
  const l = [...document.querySelectorAll('label')].find((l) => {
    const copy = l.cloneNode(true);
    copy.querySelectorAll('input,textarea,select').forEach((n) => n.remove());
    return copy.textContent.trim() === label;
  });
  assert.ok(l, label);
  return l.htmlFor ? document.getElementById(l.htmlFor) : l.querySelector('input,textarea,select');
};
const visible = (node) => !node.closest('[hidden]');
async function change(input, value) {
  await React.act(() => {
    Object.getOwnPropertyDescriptor(input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new window.Event('input', { bubbles: true }));
  });
}
async function click(text) {
  const b = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === text);
  assert.ok(b, text); await React.act(() => b.click());
}
let mountedRoot;
test.afterEach(async () => {
  if (mountedRoot) await React.act(() => mountedRoot.unmount());
  mountedRoot = null;
});
async function mount(Component, p) {
  const root = createRoot(document.getElementById('root'));
  mountedRoot = root;
  await React.act(() => root.render(React.createElement(Component, p)));
  return root;
}

test('workspace mode defaults to Basic, survives remount and stays independent of other workspaces', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  let root = await mount(GeneratorExport, props(generatorProject));
  assert.equal(mode('Basic')?.getAttribute('aria-checked'), 'true', 'Basic is the default');
  await click('Professional');
  await React.act(() => root.unmount());
  root = await mount(GeneratorExport, props(generatorProject));
  assert.equal(mode('Professional')?.getAttribute('aria-checked'), 'true');
  await React.act(() => root.unmount());
  root = await mount(CreativeWorkspace, props());
  assert.equal(mode('Basic')?.getAttribute('aria-checked'), 'true', 'Directing has its own preference');
  await React.act(() => root.unmount());
});

test('keyboard mode switching preserves custom generator draft and submits it from Basic', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  let sent;
  global.fetch = async (_url, options) => { sent = JSON.parse(options.body); return { ok: true, json: async () => generatorProject }; };
  const root = await mount(GeneratorExport, props(generatorProject));
  assert.ok(mode('Basic'), 'A mode switch is available');
  assert.equal(visible(field('Custom video prompt template')), false);
  await React.act(() => {
    mode('Basic').focus();
    mode('Basic').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  });
  assert.equal(mode('Professional').getAttribute('aria-checked'), 'true');
  assert.equal(document.activeElement, mode('Professional'));
  const input = field('Custom video prompt template');
  await change(input, 'Portrait {motion}');
  await click('Basic');
  assert.equal(visible(input), false);
  assert.equal(input.value, 'Portrait {motion}');
  assert.equal(sent, undefined, 'Mode changes never call a project mutation');
  await click('Apply generator choices');
  assert.equal(sent.arguments.settings.custom_video_template, 'Portrait {motion}');
  assert.equal(sent.arguments.expected_revision, project.revision);
  await React.act(() => root.unmount());
});

test('Basic directing keeps help, references, continuity and QC while Professional restores detailed fields', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  const root = await mount(CreativeWorkspace, props());
  assert.ok(mode('Basic'), 'A directing mode switch is available');
  await click('Camera');
  assert.equal(visible(field('Lens feel')), true);
  assert.ok(document.querySelector('[aria-label="Help: Lens feel"]'));
  assert.equal(visible(field('Movement timing')), false);
  await click('Professional');
  const detail = field('Movement timing');
  await change(detail, 'Start at second two');
  await click('Basic');
  await click('Professional');
  assert.equal(field('Movement timing').value, 'Start at second two');
  await click('Basic');
  await click('References'); assert.equal(visible(field('Generation mode')), true);
  await click('Continuity'); assert.equal(visible(field('Primary action')), true);
  await click('Quality'); assert.equal(visible(field('Acceptance criteria (one per line)')), true);
  assert.ok(document.querySelector('.cv-checks'));
  await React.act(() => root.unmount());
});

test('Basic production keeps budgets and QC while preserving detailed project defaults', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  global.fetch = async () => ({ ok: true, json: async () => ({}) });
  const root = await mount(ProductionWorkspace, { ...props(), view: 'production' });
  assert.ok(mode('Basic'), 'A production mode switch is available');
  assert.equal(visible(field('Total budget')), true);
  assert.equal(visible(field('Maximum attempts per shot and media kind')), true);
  assert.ok([...document.querySelectorAll('label')].some((l) => l.textContent.includes('Require recorded media checks')));
  assert.equal(visible(field('Project lens feel')), true);
  assert.equal(visible(field('Project movement speed')), false);
  await click('Professional');
  await change(field('Project movement speed'), 'Slow');
  await click('Basic');
  assert.equal(field('Project movement speed').value, 'Slow');
  assert.equal(visible(field('Project movement speed')), false);
  await React.act(() => root.unmount());
});

test('mode changes still work when preference storage rejects writes', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  const root = await mount(GeneratorExport, props(generatorProject));
  const original = window.Storage.prototype.setItem;
  window.Storage.prototype.setItem = () => { throw new Error('Quota exceeded'); };
  try {
    await click('Professional');
    assert.equal(mode('Professional').getAttribute('aria-checked'), 'true');
    assert.equal(visible(field('Custom video prompt template')), true);
    await click('Basic');
    assert.equal(mode('Basic').getAttribute('aria-checked'), 'true');
  } finally {
    window.Storage.prototype.setItem = original;
    await React.act(() => root.unmount());
  }
});

test('image projects hide video setup and retain editable image model in Basic', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  await mount(GeneratorExport, props({...generatorProject, output_type:'image', settings:{...generatorProject.settings,image_model:'Flux 2'}}));
  assert.ok(![...document.querySelectorAll('label')].some(l=>l.textContent.includes('Video generator template')));
  assert.equal(field('Image model name').value,'Flux 2');
  await change(field('Image model name'),'Custom image model');
  await click('Apply generator choices');
});

test('image directing removes motion, narration and timing inputs', async () => {
  window.localStorage.clear(); window.sessionStorage.clear();
  await mount(CreativeWorkspace, props({...project,output_type:'image'}));
  for(const text of ['Motion / base prompt','Narration','Generation duration (seconds)']) assert.ok(![...document.querySelectorAll('label')].some(l=>l.textContent.trim()===text),text);
  assert.ok(field('Visual concept'));
});
