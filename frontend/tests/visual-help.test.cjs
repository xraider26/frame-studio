// DOM component verification without launching/controlling an external browser.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { JSDOM } = require("jsdom");
const compiled = path.resolve(__dirname, "../.studio-test/components");
const built = spawnSync(
  process.execPath,
  [
    require.resolve("typescript/bin/tsc"),
    "src/app/studio/visual-help.tsx",
    "src/app/studio/creative-forms.tsx",
    "src/app/studio/creative-workspace.tsx",
    "src/app/studio/generator-export.tsx",
    "--outDir",
    compiled,
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
assert.equal(built.status, 0, built.stdout + built.stderr);
const dom = new JSDOM('<!doctype html><body><div id="root"></div></body>', {
  url: "http://localhost",
  pretendToBeVisual: true,
});
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
const { VisualHelp, TechniqueVisual } = require(
  path.join(compiled, "visual-help.js"),
);
const { reconcile, useDraft } = require(
  path.join(compiled, "creative-forms.js"),
);
const { CreativeWorkspace } = require(
  path.join(compiled, "creative-workspace.js"),
);
const { GeneratorExport } = require(path.join(compiled, "generator-export.js"));
const entry = {
  id: "digital",
  category: "camera",
  name: "Digital cinema",
  explanation: "Clean highlight roll-off",
  use_when: "Controlled narrative scene",
  risk: "A look is not a lighting setup",
  source_note: "Illustrative studio reference",
  apply: { camera: { body_look: "Digital cinema" } },
  visual: { kind: "camera", variant: "digital" },
};

test("hover, click pin, example apply, focus and Escape work in the actual React component", async () => {
  const root = createRoot(document.getElementById("root"));
  let applied = null;
  await React.act(() =>
    root.render(
      React.createElement(VisualHelp, {
        label: "Camera look",
        category: "camera",
        entries: [entry],
        onApply: (e) => (applied = e),
      }),
    ),
  );
  const button = document.querySelector('[aria-label="Help: Camera look"]');
  await React.act(() =>
    button.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true })),
  );
  assert.ok(
    document.querySelector('[role="dialog"]'),
    "hover opens visual help",
  );
  assert.ok(
    document.querySelector('svg[role="img"]'),
    "help contains an actual visual",
  );
  await React.act(() =>
    button.dispatchEvent(
      new window.MouseEvent("click", { bubbles: true, detail: 1 }),
    ),
  );
  await React.act(async () => {
    button.dispatchEvent(
      new window.MouseEvent("mouseout", {
        bubbles: true,
        relatedTarget: document.body,
      }),
    );
    await new Promise((r) => setTimeout(r, 220));
  });
  assert.ok(
    document.querySelector('[role="dialog"]'),
    "clicked help remains pinned after pointer leaves",
  );
  await React.act(() =>
    window.dispatchEvent(
      new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    ),
  );
  assert.equal(
    document.querySelector('[role="dialog"]'),
    null,
    "Escape closes without focus reopening it",
  );
  await React.act(() => {
    button.blur();
    button.focus();
  });
  assert.ok(
    document.querySelector('[role="dialog"]'),
    "keyboard focus opens help",
  );
  const apply = [...document.querySelectorAll("button")].find(
    (b) => b.textContent === "Use this technique",
  );
  await React.act(() => apply.click());
  assert.equal(applied.id, "digital");
  assert.equal(document.querySelector('[role="dialog"]'), null);
  await React.act(() => root.unmount());
});

test("mobile help is clamped and outside pointer dismisses", async () => {
  Object.defineProperty(window, "innerWidth", {
    value: 390,
    configurable: true,
  });
  Object.defineProperty(window, "innerHeight", {
    value: 844,
    configurable: true,
  });
  const root = createRoot(document.getElementById("root"));
  await React.act(() =>
    root.render(
      React.createElement(VisualHelp, {
        label: "Lens feel",
        category: "lens",
        value: "custom",
        entries: [],
      }),
    ),
  );
  const button = document.querySelector('[aria-label="Help: Lens feel"]');
  button.getBoundingClientRect = () => ({ left: 370, bottom: 820 });
  await React.act(() => button.click());
  const panel = document.querySelector('[role="dialog"]');
  assert.ok(
    parseInt(panel.style.left) >= 12 && parseInt(panel.style.left) <= 24,
  );
  assert.ok(parseInt(panel.style.top) + 560 <= 844);
  assert.match(panel.textContent, /Custom direction/);
  await React.act(() =>
    document.body.dispatchEvent(
      new window.Event("pointerdown", { bubbles: true }),
    ),
  );
  assert.equal(document.querySelector('[role="dialog"]'), null);
  await React.act(() => root.unmount());
});

test("rebase preserves unrelated remote fields and entries while retaining edited fields", () => {
  const base = {
    shots: [{ id: "a", lens: "35", light: "soft" }],
    brief: { promise: "old", audience: "all" },
  };
  const local = {
    shots: [{ id: "a", lens: "85", light: "soft" }],
    brief: { promise: "local", audience: "all" },
  };
  const remote = {
    shots: [
      { id: "a", lens: "35", light: "hard" },
      { id: "b", lens: "24" },
    ],
    brief: { promise: "old", audience: "creators" },
  };
  const result = reconcile(base, local, remote);
  assert.equal(result.shots[0].lens, "85");
  assert.equal(result.shots[0].light, "hard");
  assert.equal(result.shots[1].id, "b");
  assert.equal(result.brief.promise, "local");
  assert.equal(result.brief.audience, "creators");
});

test("illustration distinguishes lens, lighting and movement examples with accessible labels", async () => {
  const root = createRoot(document.getElementById("root"));
  for (const [kind, variant] of [
    ["lens", "telephoto"],
    ["lighting", "rim"],
    ["movement", "orbit"],
  ]) {
    await React.act(() =>
      root.render(React.createElement(TechniqueVisual, { kind, variant })),
    );
    assert.equal(
      document.querySelector("svg").getAttribute("aria-label"),
      `${kind} illustration: ${variant}`,
    );
    assert.match(
      document.querySelector("figcaption").textContent,
      /not a generator prediction/,
    );
  }
  await React.act(() => root.unmount());
});

test("angle and retreat examples visibly differ from their default scene", async () => {
  const root = createRoot(document.getElementById("root"));
  const markup = async (kind, variant) => {
    await React.act(() =>
      root.render(React.createElement(TechniqueVisual, { kind, variant })),
    );
    return [...document.querySelectorAll("svg path")]
      .map((p) => p.getAttribute("d"))
      .join("|");
  };
  assert.notEqual(
    await markup("movement", "out"),
    await markup("movement", "pan"),
  );
  assert.notEqual(
    await markup("framing", "high"),
    await markup("framing", "medium"),
  );
  await React.act(() => root.unmount());
});

test("real shot inspector saves overrides and can distinguish multiple unsaved shots", async () => {
  const fixture = spawnSync(
    path.resolve(__dirname, "../../backend/.venv/Scripts/python.exe"),
    [
      "-c",
      "import json,tempfile;from pathlib import Path;from studio.workflow import Studio;from studio.knowledge import knowledge_catalog;t=tempfile.TemporaryDirectory();r=Path(t.name);s=Studio(r/'db',r/'media',r/'inbox');p=s.create_project('Fixture','ai-film');print(json.dumps({'project':s.get_project(p['id']),'catalog':knowledge_catalog()}))",
    ],
    { cwd: path.resolve(__dirname, "../../backend"), encoding: "utf8" },
  );
  assert.equal(fixture.status, 0, fixture.stderr);
  const data = JSON.parse(fixture.stdout);
  const root = createRoot(document.getElementById("root"));
  let sent;
  global.fetch = async (url, options) => {
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ ...data.project, revision: 2 }) };
  };
  const save = async (fn) => fn();
  await React.act(() =>
    root.render(
      React.createElement(CreativeWorkspace, {
        ...data,
        busy: false,
        inbox: "test-inbox",
        save,
      }),
    ),
  );
  const click = async (text) => {
    const b = [...document.querySelectorAll("button")].find(
      (b) => b.textContent.trim() === text,
    );
    assert.ok(b, text);
    await React.act(() => b.click());
  };
  const field = (label) => {
    const l = [...document.querySelectorAll("label")].find(
      (x) => x.textContent === label,
    );
    assert.ok(l, label);
    return document.getElementById(l.htmlFor);
  };
  await click("Camera");
  const lens = field("Lens feel");
  await React.act(() => {
    Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    ).set.call(lens, "85mm portrait feel");
    lens.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await click("Apply shot direction");
  assert.equal(sent.operation, "update_shots");
  assert.equal(
    sent.arguments.shots[0].direction.camera.lens,
    "85mm portrait feel",
  );
  await click("Add");
  await click("Add");
  assert.equal(
    field("Shot title").value,
    "Shot 5",
    "Second unsaved shot must be distinct from the first",
  );
  await React.act(() => root.unmount());
});

test("unapplied drafts survive navigation/remount and retain their conflict revision", async () => {
  function Probe({ revision }) {
    const form = useDraft(
      React.useMemo(() => ({ lens: "35mm" }), []),
      revision,
      "draft-probe",
    );
    return React.createElement(
      "button",
      { onClick: () => form.edit((v) => ({ ...v, lens: "85mm" })) },
      form.draft.lens + " / " + form.conflict,
    );
  }
  let root = createRoot(document.getElementById("root"));
  await React.act(() =>
    root.render(React.createElement(Probe, { revision: 1 })),
  );
  await React.act(() => document.querySelector("button").click());
  await React.act(() => root.unmount());
  root = createRoot(document.getElementById("root"));
  await React.act(() =>
    root.render(React.createElement(Probe, { revision: 2 })),
  );
  assert.equal(document.querySelector("button").textContent, "85mm / true");
  await React.act(() => root.unmount());
  window.sessionStorage.clear();
});

test("rebasing multiple new shots uses their distinct client draft keys", () => {
  const base = [{ id: "a", title: "Existing", light: "soft" }];
  const local = [
    ...base,
    { id: "", _draft_key: "new-1", title: "First new" },
    { id: "", _draft_key: "new-2", title: "Second new" },
  ];
  const remote = [{ id: "a", title: "Existing", light: "hard" }];
  const merged = reconcile(base, local, remote);
  assert.equal(merged[0].light, "hard");
  assert.equal(merged[1].title, "First new");
  assert.equal(merged[2].title, "Second new");
});

test("generator templates survive remount, rebase remote changes and save the latest revision", async () => {
  window.sessionStorage.clear();
  let project = {
    id: "generator-probe",
    revision: 1,
    settings: {
      generation_mode: "external_agent",
      video_generator: "custom",
      image_generator: "custom",
      custom_video_template: "{motion}",
      custom_image_template: "{subject}",
    },
    preflight: { issues: [], errors: 0, warnings: 0 },
    shots: [],
  };
  const profiles = [{ id: "custom", name: "Custom", hint: "Custom profile" }];
  let root = createRoot(document.getElementById("root")),
    sent;
  const props = () => ({
    project,
    videoProfiles: profiles,
    imageProfiles: profiles,
    busy: false,
    save: async (fn) => fn(),
  });
  const render = async () =>
    React.act(() => root.render(React.createElement(GeneratorExport, props())));
  await render();
  const input = document.querySelector("textarea");
  await React.act(() => {
    Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value",
    ).set.call(input, "Artistic {motion}");
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await React.act(() => root.unmount());
  project = {
    ...project,
    revision: 2,
    settings: {
      ...project.settings,
      custom_image_template: "Remote {subject}",
    },
  };
  root = createRoot(document.getElementById("root"));
  await render();
  assert.equal(document.querySelector("textarea").value, "Artistic {motion}");
  const rebase = [...document.querySelectorAll("button")].find((b) =>
    b.textContent.includes("Rebase my draft"),
  );
  assert.ok(rebase, "Remote changes offer explicit recovery");
  await React.act(() => rebase.click());
  assert.equal(
    document.querySelectorAll("textarea")[1].value,
    "Remote {subject}",
  );
  global.fetch = async (url, options) => {
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ ...project, revision: 3 }) };
  };
  await React.act(() =>
    [...document.querySelectorAll("button")]
      .find((b) => b.textContent.includes("Apply generator choices"))
      .click(),
  );
  assert.equal(sent.arguments.expected_revision, 2);
  assert.equal(
    sent.arguments.settings.custom_video_template,
    "Artistic {motion}",
  );
  await React.act(() => root.unmount());
  window.sessionStorage.clear();
});
