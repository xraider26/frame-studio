const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { JSDOM } = require("jsdom");
const out = path.resolve(__dirname, "../.studio-test/template-sequence");
const compiled = spawnSync(
  process.execPath,
  [
    require.resolve("typescript/bin/tsc"),
    "src/app/studio/template-hub.tsx",
    "src/app/studio/sequence-workspace.tsx",
    "--outDir",
    out,
    "--jsx",
    "react-jsx",
    "--module",
    "commonjs",
    "--target",
    "ES2022",
    "--esModuleInterop",
    "--skipLibCheck",
  ],
  { cwd: path.resolve(__dirname, ".."), encoding: "utf8" },
);
assert.equal(compiled.status, 0, compiled.stdout + compiled.stderr);
const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost" });
Object.assign(global, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node,
  IS_REACT_ACT_ENVIRONMENT: true,
});
Object.defineProperty(global, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
const React = require("react");
const { createRoot } = require("react-dom/client");
const { TemplateHub } = require(path.join(out, "template-hub.js"));
const { SequenceWorkspace } = require(path.join(out, "sequence-workspace.js"));
let root;
async function mount(Component, props) {
  root = createRoot(document.getElementById("root"));
  await React.act(async () =>
    root.render(React.createElement(Component, props)),
  );
}
test.afterEach(async () => {
  if (root) await React.act(() => root.unmount());
  root = null;
  window.sessionStorage.clear();
});
async function click(text) {
  const button = [...document.querySelectorAll("button")].find(
    (b) => b.textContent.trim() === text,
  );
  assert.ok(button, `Button ${text}`);
  await React.act(async () => button.click());
}
function recipe(id, name, output_type) {
  return {
    id,
    name,
    output_type,
    version: 1,
    intent: "An editable creative plan",
    references: ["Canonical subject"],
    planning: ["Choose the intended result"],
    decision_requirements: [],
    roles: [],
    image_checks: ["Identity matches"],
    video_checks: output_type === "video" ? ["Motion coherent"] : [],
    final_checks: [],
    source_rules: [],
    stages: { brief: ["Choose the idea"] },
    examples: [],
  };
}
const choices = [
  {
    id: "short-drama",
    name: "Short drama",
    output_type: "video",
    description: "Story",
    structure: [],
    aspect: "9:16",
  },
  {
    id: "image-portrait",
    name: "Portrait study",
    output_type: "image",
    description: "Portrait",
    structure: [],
    aspect: "1:1",
  },
];

test("template media switch filters recipes and carries image type into creation", async () => {
  const calls = [],
    created = [];
  global.fetch = async (u, o) => {
    const c = JSON.parse(o.body);
    calls.push(c.operation);
    return {
      ok: true,
      json: async () => ({
        recipes: [
          recipe("short-drama", "Short drama", "video"),
          recipe("image-portrait", "Portrait study", "image"),
        ],
        coverage: { review_status: "Partial" },
      }),
    };
  };
  await mount(TemplateHub, {
    project: null,
    choices,
    busy: false,
    save: async (fn) => fn(),
    onNew: (...args) => created.push(args),
  });
  await click("Image");
  assert.match(document.body.textContent, /Portrait study/);
  assert.ok(!document.body.textContent.includes("Short drama"));
  await click("Use for new project");
  assert.deepEqual(created, [["image-portrait", "image"]]);
  assert.ok(calls.every((op) => op === "recipe_catalog"));
  assert.ok(!document.body.textContent.includes("Video acceptance"));
});

test("saved image templates do not mix with video templates", async () => {
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ recipes: [], coverage: {} }),
  });
  const saved = [
    {
      ...choices[0],
      id: "saved-video",
      saved: true,
      revision: 1,
      sections: ["settings"],
    },
    {
      ...choices[1],
      id: "saved-image",
      name: "My portrait light",
      saved: true,
      revision: 1,
      sections: ["settings"],
    },
  ];
  await mount(TemplateHub, {
    project: null,
    choices: saved,
    busy: false,
    save: async (fn) => fn(),
    onNew: () => {},
  });
  await click("Image");
  await click("Saved");
  assert.match(document.body.textContent, /My portrait light/);
  assert.ok(!document.body.textContent.includes("Short drama"));
});

test("sequence browsing previews actual allocation and requires replacement confirmation", async () => {
  let applied;
  const pattern = {
    id: "creator-explainer",
    name: "Creator explainer",
    description: "A-roll and supporting B-roll",
    roles: [
      {
        id: "main",
        title: "Main explanation",
        coverage_role: "a_roll",
        purpose: "Deliver the main idea",
        weight: 2,
        transition_in: "cut",
        audio_continuity: "Speech carries over B-roll",
      },
      {
        id: "support",
        title: "Supporting detail",
        coverage_role: "b_roll",
        purpose: "Show the evidence",
        weight: 1,
        transition_in: "l_cut",
        audio_continuity: "Use main speech",
        source_role_id: "main",
      },
    ],
    technique_notes: ["A-roll carries the message; B-roll adds evidence."],
  };
  global.fetch = async (u, o) => {
    const c = JSON.parse(o.body);
    if (c.operation === "sequence_catalog")
      return {
        ok: true,
        json: async () => ({ sequences: [pattern], planning_only: true }),
      };
    if (c.operation === "preview_sequence")
      return {
        ok: true,
        json: async () => ({
          source_revision: 9,
          sequence_id: pattern.id,
          roles: [
            {
              title: "Main explanation",
              duration_seconds: 20,
              direction: { editorial: { coverage_role: "a_roll" } },
            },
            {
              title: "Supporting detail",
              duration_seconds: 10,
              direction: { editorial: { coverage_role: "b_roll" } },
            },
          ],
          shot_count: 2,
          replacement_required: true,
          existing_work: { shots: 3, assets: 1, documents: 2 },
        }),
      };
    applied = c;
    return { ok: true, json: async () => ({}) };
  };
  await mount(SequenceWorkspace, {
    project: {
      id: "p1",
      revision: 9,
      output_type: "video",
      settings: { duration_seconds: 30 },
      shots: [{ id: "s1" }],
      production: { story: {} },
    },
    busy: false,
    save: async (fn) => fn(),
  });
  const apply = [...document.querySelectorAll("button")].find(
    (b) => b.textContent.trim() === "Apply sequence",
  );
  assert.ok(apply);
  assert.equal(apply.disabled, true);
  assert.match(document.body.textContent, /B-roll/);
  assert.match(document.body.textContent, /20s/);
  const checkbox = document.querySelector("input[type=checkbox]");
  assert.ok(checkbox);
  await React.act(() => checkbox.click());
  await click("Apply sequence");
  assert.equal(applied.operation, "apply_sequence");
  assert.deepEqual(applied.arguments, {
    project_id: "p1",
    sequence_id: "creator-explainer",
    expected_revision: 9,
    confirm_replace: true,
  });
});

test("image projects never offer video sequence application", async () => {
  let calls = 0;
  global.fetch = async () => {
    calls++;
    return { ok: true, json: async () => ({ sequences: [] }) };
  };
  await mount(SequenceWorkspace, {
    project: { id: "p1", revision: 1, output_type: "image" },
    busy: false,
    save: async (fn) => fn(),
  });
  assert.equal(calls, 0);
  assert.ok(
    ![...document.querySelectorAll("button")].some(
      (b) => b.textContent === "Apply sequence",
    ),
  );
});
