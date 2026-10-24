const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { JSDOM } = require("jsdom");
const out = path.resolve(__dirname, "../.studio-test/next-beta");
const build = spawnSync(
  process.execPath,
  [
    require.resolve("typescript/bin/tsc"),
    "src/app/studio/creative-brief.tsx",
    "src/app/studio/media-upload.tsx",
    "src/app/studio/takes-workspace.tsx",
    "--outDir",
    out,
    "--jsx",
    "react-jsx",
    "--module",
    "commonjs",
    "--target",
    "ES2023",
    "--esModuleInterop",
    "--skipLibCheck",
  ],
  { cwd: path.resolve(__dirname, ".."), encoding: "utf8" },
);
assert.equal(build.status, 0, build.stdout + build.stderr);
const dom = new JSDOM('<div id="root"></div>', { url: "http://localhost" });
Object.assign(global, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  Node: dom.window.Node,
  FormData: dom.window.FormData,
  IS_REACT_ACT_ENVIRONMENT: true,
});
Object.defineProperty(global, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
const React = require("react");
const { createRoot } = require("react-dom/client");
const { CreativeBrief } = require(path.join(out, "creative-brief.js"));
const { TakesWorkspace } = require(path.join(out, "takes-workspace.js"));
const { MediaUpload, ImportCostReport } = require(
  path.join(out, "media-upload.js"),
);
let root;
const project = {
  id: "p1",
  revision: 14,
  output_type: "image",
  settings: { creative_intake: { vision: "A fox by a stream" } },
  creative_intake: {
    status: "needs_input",
    questions: [{ id: "purpose", prompt: "Where will it be used?" }],
    answers: { vision: "A fox by a stream" },
  },
  shots: [{ id: "shot1", title: "Portrait" }],
};
async function mount(Component, props = {}) {
  root = createRoot(document.getElementById("root"));
  await React.act(() =>
    root.render(
      React.createElement(Component, {
        project,
        busy: false,
        save: async (fn) => fn(),
        ...props,
      }),
    ),
  );
}
test.afterEach(async () => {
  if (root) await React.act(() => root.unmount());
  root = null;
});

test("takes from earlier plans remain viewable without selecting them for a removed shot", async () => {
  await mount(TakesWorkspace, {project: {...project, next_action: {}, jobs: [], assets: [
    {id: "old-take", kind: "image", shot_id: "removed-shot", stale: true, name: "Earlier portrait", url: "/old.png", path: "old.png"}
  ]}});
  const option=[...document.querySelectorAll("option")].find(o=>o.textContent.includes("Earlier plan media"));
  assert.ok(option, "retained media selector");
  const selector=option.parentElement;
  await React.act(()=>{selector.value=option.value;selector.dispatchEvent(new window.Event("change",{bubbles:true}));});
  assert.equal(document.querySelector('img[alt="Earlier portrait"]').getAttribute("src"),"/old.png");
  assert.ok(![...document.querySelectorAll("button")].some(b=>b.textContent.includes("Select this take")));
  assert.ok(document.querySelector('a[href="/old.png"]'), "download remains available");
});
async function click(text) {
  const b = [...document.querySelectorAll("button")].find(
    (b) => b.textContent === text,
  );
  assert.ok(b, text);
  await React.act(() => b.click());
}
async function change(el, value) {
  await React.act(() => {
    Object.getOwnPropertyDescriptor(
      el.tagName === "TEXTAREA"
        ? window.HTMLTextAreaElement.prototype
        : el.tagName === "SELECT"
          ? window.HTMLSelectElement.prototype
          : window.HTMLInputElement.prototype,
      "value",
    ).set.call(el, value);
    el.dispatchEvent(
      new window.Event(el.tagName === "SELECT" ? "change" : "input", {
        bubbles: true,
      }),
    );
  });
}
test("creative answers preserve existing vision and save current revision", async () => {
  let sent;
  global.fetch = async (u, o) => {
    sent = JSON.parse(o.body);
    return { ok: true, json: async () => ({}) };
  };
  await mount(CreativeBrief);
  assert.match(
    document.querySelector("[role=status]").textContent,
    /Where will it be used/,
  );
  const fields = document.querySelectorAll("textarea");
  assert.equal(fields[0].value, "A fox by a stream");
  await change(fields[1], "Watercolour");
  await change(fields[2], "Book cover");
  await click("Save creative brief");
  assert.equal(sent.operation, "update_settings");
  assert.equal(sent.arguments.expected_revision, 14);
  assert.deepEqual(sent.arguments.settings.creative_intake, {
    vision: "A fox by a stream",
    art_style: "Watercolour",
    purpose: "Book cover",
  });
});
test("external image is uploaded as a shot take without claiming generation", async () => {
  let request;
  global.fetch = async (url, options) => {
    request = { url, ...options };
    return { ok: true, json: async () => ({}) };
  };
  await mount(MediaUpload);
  const input = document.querySelector("input[type=file]");
  assert.equal(input.accept, "image/*");
  const file = new window.File(["bytes"], "portrait.png", {
    type: "image/png",
  });
  Object.defineProperty(input, "files", { value: [file] });
  await React.act(() =>
    input.dispatchEvent(new window.Event("change", { bubbles: true })),
  );
  await click("Upload shot take");
  assert.equal(request.url, "/api/studio/upload");
  assert.equal(request.body.get("role"), "take");
  assert.equal(request.body.get("kind"), "image");
  assert.equal(request.body.get("shot_id"), "shot1");
  assert.equal(request.body.get("expected_revision"), "14");
});
test("entity upload binds reference to the entity and rejects dropped video", async () => {
  let sent;
  global.fetch = async (url, o) => {
    sent = o.body;
    return { ok: true, json: async () => ({}) };
  };
  await mount(MediaUpload, { entityId: "fox" });
  const input = document.querySelector("input[type=file]");
  Object.defineProperty(input, "files", {
    configurable: true,
    value: [new window.File(["video"], "clip.mp4", { type: "video/mp4" })],
  });
  await React.act(() =>
    input.dispatchEvent(new window.Event("change", { bubbles: true })),
  );
  assert.match(document.querySelector("[role=alert]").textContent, /image/);
  Object.defineProperty(input, "files", {
    value: [new window.File(["image"], "fox.png", { type: "image/png" })],
  });
  await React.act(() =>
    input.dispatchEvent(new window.Event("change", { bubbles: true })),
  );
  await click("Upload reference");
  assert.equal(sent.get("entity_id"), "fox");
  assert.equal(sent.get("role"), "reference");
});

test("external take cost can be reported without inventing a generation job", async () => {
  let sent;
  global.fetch = async (u, o) => {
    sent = JSON.parse(o.body);
    return { ok: true, json: async () => ({}) };
  };
  await mount(ImportCostReport, {
    asset: {
      id: "imported1",
      provenance: { type: "externally_created" },
      cost: { actual: null, unit: "credits", evidence: "" },
    },
  });
  await change(document.querySelector("input[type=number]"), "0");
  await change(
    document.querySelector("textarea"),
    "Created locally, no provider charge",
  );
  await click("Record imported take cost");
  assert.equal(sent.operation, "record_import_cost");
  assert.equal(sent.arguments.asset_id, "imported1");
  assert.equal(sent.arguments.actual, 0);
  assert.equal(sent.arguments.expected_revision, 14);
  assert.ok(!("job_id" in sent.arguments));
});
