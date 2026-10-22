const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const { JSDOM } = require("jsdom");
const component = path.resolve(
  __dirname,
  "../src/app/studio/queue-workspace.tsx",
);
const compiled = path.resolve(__dirname, "../.studio-test/queue");
if (existsSync(component)) {
  const built = spawnSync(
    process.execPath,
    [
      require.resolve("typescript/bin/tsc"),
      component,
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
}
const dom = new JSDOM('<!doctype html><div id="root"></div>', {
  url: "http://localhost",
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
const QueueWorkspace = existsSync(component)
  ? require(path.join(compiled, "queue-workspace.js")).QueueWorkspace
  : null;
const batch = {
  id: "batch-a",
  revision: 4,
  name: "Rain walks",
  idea: "A walker finds something different each day",
  kind: "episodes",
  project_ids: ["project-a"],
  paused: false,
  max_parallel: 2,
  budget_limit: null,
  unit: "credits",
  image_cost: null,
  video_cost: null,
  cost_evidence: "",
  auto_retry: false,
  retry_limit: 2,
  identity_version: 1,
  identity_source_project_id: "source-a",
  reserved_or_spent: 12,
  unknown_cost_jobs: 1,
};
const item = {
  project_id: "project-a",
  project_name: "Rain walk 01",
  revision: 7,
  batch_id: "batch-a",
  priority: 0,
  dispatch_paused: false,
  state: "awaiting_approval",
  actionable: false,
  next_action: {
    action: "await_approval",
    step: "brief",
    message: "Review the written brief",
  },
  message: "Review the written brief",
  lease: null,
  active_jobs: 0,
  reserved_or_spent: 12,
  unknown_cost_jobs: 1,
  unit: "credits",
  failures: 2,
  identity_version: 1,
  quality_retries: 1,
};
let root, calls, failCreate, selected, changes, queueResponse;
test.beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  calls = [];
  failCreate = false;
  changes = 0;
  queueResponse = {
    items: [item],
    batches: [batch],
    instructions: "Connect an agent through MCP.",
  };
  global.fetch = async (_url, options) => {
    const sent = JSON.parse(options.body);
    calls.push(sent);
    if (sent.operation === "production_queue")
      return { ok: true, json: async () => queueResponse };
    if (sent.operation === "create_batch" && failCreate)
      return {
        ok: false,
        json: async () => ({ message: "Temporary connection failure" }),
      };
    return { ok: true, json: async () => batch };
  };
});
test.afterEach(async () => {
  if (root) await React.act(() => root.unmount());
  root = null;
});
async function mount() {
  assert.equal(
    typeof QueueWorkspace,
    "function",
    "The production queue workspace must be available",
  );
  root = createRoot(document.getElementById("root"));
  await React.act(() =>
    root.render(
      React.createElement(QueueWorkspace, {
        templates: [
          { id: "ai-film", name: "Film" },
          { id: "saved-a", name: "Saved portrait", saved: true },
        ],
        projects: [{ id: "source-a", name: "Identity source", revision: 9 }],
        onSelect: (id) => {
          selected = id;
        },
        onChanged: () => {
          changes++;
        },
      }),
    ),
  );
}
const field = (label) => {
  const l = [...document.querySelectorAll("label")].find((l) => {
    const copy = l.cloneNode(true);
    copy.querySelectorAll("input,textarea,select").forEach((n) => n.remove());
    return copy.textContent.trim() === label;
  });
  assert.ok(l, label);
  return l.htmlFor
    ? document.getElementById(l.htmlFor)
    : l.querySelector("input,textarea,select");
};
async function change(label, value) {
  const input = field(label);
  await React.act(() => {
    const proto =
      input.tagName === "TEXTAREA"
        ? window.HTMLTextAreaElement.prototype
        : input.tagName === "SELECT"
          ? window.HTMLSelectElement.prototype
          : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(input, value);
    input.dispatchEvent(
      new window.Event(input.tagName === "SELECT" ? "change" : "input", {
        bubbles: true,
      }),
    );
  });
}
async function click(text) {
  const button = [...document.querySelectorAll("button")].find(
    (b) =>
      b.textContent.trim() === text || b.getAttribute("aria-label") === text,
  );
  assert.ok(button, text);
  await React.act(() => button.click());
}
const command = (operation) =>
  calls.filter((c) => c.operation === operation).at(-1);

test("an idea launches five independent episodes with explicit template and safe default policy", async () => {
  await mount();
  await change("Batch name", "Rain walks");
  await change("Idea", "Every day, one new discovery");
  await change("Template recipe", "saved-a");
  await click("Create production batch");
  const sent = command("create_batch");
  assert.equal(sent.actor, "user");
  assert.equal(sent.arguments.idea, "Every day, one new discovery");
  assert.equal(sent.arguments.template_id, "saved-a");
  assert.equal(sent.arguments.kind, "episodes");
  assert.equal(sent.arguments.count, 5);
  assert.equal(sent.arguments.policy.max_parallel, 2);
  assert.equal(sent.arguments.policy.auto_retry, false);
  assert.equal(sent.arguments.policy.retry_limit, 2);
  assert.ok(sent.arguments.request_id);
  assert.equal(changes, 1);
});

test("an idea alone supplies the batch name and queue instructions match actual MCP signatures", async () => {
  await mount();
  await change("Idea", "A traveler explores quiet observatories");
  await click("Create production batch");
  assert.equal(
    command("create_batch")?.arguments.name,
    "A traveler explores quiet observatories",
  );
  assert.doesNotMatch(
    field("Agent queue instructions").value,
    /task_id, actor/,
  );
});

test("creation retries preserve the request key and optional briefs plus canonical source revision", async () => {
  await mount();
  await click("Professional");
  await change("Batch name", "Two portraits");
  await change("Idea", "Two versions of one portrait");
  await change("Number of items", "2");
  await change("Batch kind", "variations");
  await change("Per-item briefs (one per line)", "In rain\nAt sunset");
  await change("Canonical identity source", "source-a");
  failCreate = true;
  await click("Create production batch");
  const first = command("create_batch");
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /Temporary connection failure/,
  );
  assert.equal(field("Idea").value, "Two versions of one portrait");
  failCreate = false;
  await click("Create production batch");
  const second = command("create_batch");
  assert.equal(second.arguments.request_id, first.arguments.request_id);
  assert.deepEqual(second.arguments.briefs, ["In rain", "At sunset"]);
  assert.equal(second.arguments.identity_source_project_id, "source-a");
  assert.equal(second.arguments.source_revision, 9);
});

test("policy, pause, priority and identity changes are explicit and use current revisions", async () => {
  await mount();
  await change("Batch budget · Rain walks", "80");
  assert.equal(
    command("update_batch"),
    undefined,
    "Editing never saves policy automatically",
  );
  await click("Apply batch policy · Rain walks");
  assert.equal(command("update_batch").arguments.expected_revision, 4);
  assert.equal(command("update_batch").arguments.policy.budget_limit, 80);
  await click("Pause batch · Rain walks");
  assert.deepEqual(command("update_batch").arguments.policy, { paused: true });
  await change("Priority · Rain walk 01", "6");
  await click("Apply priority · Rain walk 01");
  assert.deepEqual(command("set_project_dispatch").arguments, {
    project_id: "project-a",
    paused: false,
    priority: 6,
    expected_revision: 7,
  });
  await click("Pause project · Rain walk 01");
  assert.equal(command("set_project_dispatch").arguments.paused, true);
  await click("Sync shared identity · Rain walks");
  assert.deepEqual(command("sync_batch_identity").arguments, {
    batch_id: "batch-a",
    source_project_id: "source-a",
    expected_revision: 4,
    source_revision: 9,
  });
});

test("queue exposes real approval waits, failures, unknown costs and the existing project", async () => {
  await mount();
  const row = document.querySelector('[data-project-id="project-a"]');
  assert.ok(row);
  assert.match(row.textContent, /Needs your approval/);
  assert.match(row.textContent, /Review the written brief/);
  assert.match(row.textContent, /1 unknown cost/);
  assert.match(row.textContent, /2 failed/);
  assert.match(row.textContent, /Identity v1/);
  await click("Open project · Rain walk 01");
  assert.equal(selected, "project-a");
  assert.match(field("Agent queue instructions").value, /claim_queue_task/);
  assert.match(field("Agent queue instructions").value, /renew_queue_task/);
  assert.match(field("Agent queue instructions").value, /finish_queue_task/);
});

test("a queue refresh preserves a dirty budget and requires explicit rebase before applying the current revision", async () => {
  await mount();
  await change("Batch budget · Rain walks", "80");
  queueResponse = {
    ...queueResponse,
    batches: [{ ...batch, revision: 5, budget_limit: 20, max_parallel: 4 }],
  };
  await click("Refresh queue");
  assert.equal(field("Batch budget · Rain walks").value, "80");
  const apply = document.querySelector(
    '[aria-label="Apply batch policy · Rain walks"]',
  );
  assert.equal(apply.disabled, true);
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /draft is preserved/,
  );
  await click("Rebase my draft");
  await click("Apply batch policy · Rain walks");
  assert.equal(command("update_batch").arguments.expected_revision, 5);
  assert.equal(command("update_batch").arguments.policy.budget_limit, 80);
  assert.equal(command("update_batch").arguments.policy.max_parallel, 4);
});

test("invalid batch counts and mismatched item briefs cannot create partial work", async () => {
  await mount();
  await click("Professional");
  await change("Batch name", "Invalid batch");
  await change("Idea", "A real idea");
  await change("Number of items", "101");
  await click("Create production batch");
  assert.equal(command("create_batch"), undefined);
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /1 to 100/,
  );
  await change("Number of items", "2");
  await change("Per-item briefs (one per line)", "Only one");
  await click("Create production batch");
  assert.equal(command("create_batch"), undefined);
  assert.match(
    document.querySelector('[role="alert"]').textContent,
    /exactly one brief per item/,
  );
});
