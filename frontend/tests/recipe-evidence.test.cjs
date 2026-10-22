const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { JSDOM } = require('jsdom');
const compiled = path.resolve(__dirname, '../.studio-test/recipes');
const built = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'), 'src/app/studio/template-workspace.tsx', '--outDir', compiled, '--jsx', 'react-jsx', '--module', 'commonjs', '--target', 'ES2022', '--esModuleInterop', '--skipLibCheck'], {cwd: path.resolve(__dirname, '..'), encoding: 'utf8'});
assert.equal(built.status, 0, built.stdout + built.stderr);
const dom = new JSDOM('<body><div id="root"></div></body>', {url: 'http://localhost', pretendToBeVisual: true});
Object.assign(global, {window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Node: dom.window.Node, IS_REACT_ACT_ENVIRONMENT: true});
Object.defineProperty(global, 'navigator', {value: dom.window.navigator, configurable: true});
const React = require('react');
const {createRoot} = require('react-dom/client');
const {TemplateWorkspace} = require(path.join(compiled, 'template-workspace.js'));

test('recipe details show historical usage and send explicit human evidence with live revisions', async () => {
  const root = createRoot(document.getElementById('root'));
  const calls = [];
  const metrics = {template_id: 'saved-recipe', template_revision: 3, snapshot_hash: 'hash', source_project_id: 'source', source_project_revision: 8, settings_shot_id: '', usage_count: 2, observed_defects: 1, costs: [{unit: 'USD', reported_actual: 3, planned_unsettled: 4, unknown_actual_jobs: 1, unknown_exposure_jobs: 0}], projects: [{id: 'source', name: 'Observed film', revision: 9, source: true, attempts: 2, selected_video_shots: 1, observed_defects: 1}], evidence: [], scope: 'Historical human observations only; future output quality is untested.'};
  global.fetch = async (_url, options) => {
    const body = JSON.parse(options.body); calls.push(body);
    return {ok: true, json: async () => body.operation === 'endorse_recipe' ? {...metrics, template_revision: 4, evidence: [{id: 'e1', level: 'pilot', actor: 'user', at: '2026-10-22T00:00:00Z', note: body.arguments.note, project_id: 'source', project_revision: 9, assets: [{id: 'video-one', kind: 'video', shot_id: 's1'}], scope: 'First selected video only'}]} : metrics};
  };
  await React.act(() => root.render(React.createElement(TemplateWorkspace, {project: {id: 'source', name: 'Observed film', revision: 9, shots: []}, templates: [{id: 'saved-recipe', name: 'Recipe', description: '', saved: true, revision: 3, sections: ['settings'], aspect: '16:9', structure: []}], busy: false, save: async fn => fn(), onNew: () => {}})));
  const click = async name => {
    const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === name);
    assert.ok(button, `Missing ${name}`);
    await React.act(async () => button.click());
  };
  assert.equal(calls.length, 0, 'Recipe metrics load on demand');
  await click('Recipe evidence & usage');
  assert.match(document.body.textContent, /2 projects used this recipe/);
  assert.match(document.body.textContent, /No human endorsement/);
  assert.match(document.body.textContent, /1 job.*actual cost unknown/);
  assert.match(document.body.textContent, /Historical/);
  const note = document.querySelector('textarea[aria-label="Human review note"]');
  assert.ok(note);
  await React.act(() => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(note, 'Inspected the selected pilot.');
    note.dispatchEvent(new window.Event('input', {bubbles: true}));
  });
  await click('Record human endorsement');
  assert.deepEqual(calls.at(-1).arguments, {template_id: 'saved-recipe', project_id: 'source', note: 'Inspected the selected pilot.', expected_revision: 9, template_revision: 3, level: 'pilot'});
  assert.match(document.body.textContent, /pilot endorsement/);
  assert.match(document.body.textContent, /video-one/);
  assert.match(document.body.textContent, /source · revision 9/);
  await React.act(() => root.unmount());
});
