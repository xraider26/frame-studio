"use client";
import {generatorSettings} from "./generator-settings";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { studioApi as api } from "./client";
import { DraftNotice, Field, useDraft } from "./creative-forms";
import {
  ControlModeSwitch,
  ModeDetail,
  useControlMode,
  type ControlMode,
} from "./control-mode";

type ProjectSummary = { id: string; name: string; revision: number };
type Template = { id: string; name: string; saved?: boolean };
type Policy = {
  max_parallel: number;
  budget_limit: number | null;
  unit: string;
  image_cost: number | null;
  video_cost: number | null;
  cost_evidence: string;
  auto_retry: boolean;
  retry_limit: number;
};
type Batch = Policy & {
  id: string;
  name: string;
  idea: string;
  kind: string;
  revision: number;
  project_ids: string[];
  paused: boolean;
  identity_version: number;
  identity_source_project_id?: string;
  reserved_or_spent: number;
  unknown_cost_jobs: number;
};
type QueueItem = {
  project_id: string;
  project_name: string;
  revision: number;
  batch_id?: string;
  priority: number;
  dispatch_paused?: boolean;
  state: string;
  actionable: boolean;
  next_action: {
    action: string;
    step?: string;
    kind?: string;
    message: string;
  };
  message: string;
  lease: { actor: string; expires_at: string } | null;
  active_jobs: number;
  reserved_or_spent: number;
  unknown_cost_jobs: number;
  unit: string;
  failures: number;
  identity_version: number;
  quality_retries: number;
};
type Queue = { items: QueueItem[]; batches: Batch[]; instructions: string };
type Run = (
  operation: string,
  args: Record<string, unknown>,
  message: string,
) => Promise<boolean>;
const defaultPolicy: Policy = {
  max_parallel: 2,
  budget_limit: null,
  unit: "credits",
  image_cost: null,
  video_cost: null,
  cost_evidence: "",
  auto_retry: false,
  retry_limit: 2,
};
const stateLabels: Record<string, string> = {
  ready: "Ready for agent",
  working: "Agent working",
  waiting_output: "Waiting for real output",
  awaiting_approval: "Needs your approval",
  paused: "Paused",
  attention: "Needs attention",
  complete: "Complete",
};
function policyFrom(batch: Policy): Policy {
  return Object.fromEntries(
    Object.keys(defaultPolicy).map((key) => [key, batch[key as keyof Policy]]),
  ) as Policy;
}
function checkedPolicy(policy: Policy) {
  if (
    !Number.isInteger(policy.max_parallel) ||
    policy.max_parallel < 1 ||
    policy.max_parallel > 10
  )
    throw new Error("Parallel projects must be a whole number from 1 to 10.");
  if (
    !Number.isInteger(policy.retry_limit) ||
    policy.retry_limit < 0 ||
    policy.retry_limit > 10
  )
    throw new Error("Quality retries must be a whole number from 0 to 10.");
  if (!policy.unit.trim())
    throw new Error("Enter one cost unit for this batch.");
  for (const value of [
    policy.budget_limit,
    policy.image_cost,
    policy.video_cost,
  ])
    if (value !== null && (!Number.isFinite(value) || value < 0))
      throw new Error(
        "Budgets and planned costs must be nonnegative numbers, or blank for unknown.",
      );
  return policy;
}

function PolicyFields({
  value,
  onChange,
  suffix = "",
}: {
  value: Policy;
  onChange: (p: Policy) => void;
  suffix?: string;
}) {
  return (
    <>
      <div className="cv-form-grid">
        <Field
          label={`Parallel projects${suffix}`}
          type="number"
          value={value.max_parallel}
          onChange={(v) => onChange({ ...value, max_parallel: Number(v) })}
        />
        <Field
          label={`Cost unit${suffix}`}
          value={value.unit}
          onChange={(unit) => onChange({ ...value, unit })}
        />
        {(
          [
            ["budget_limit", "Batch budget"],
            ["image_cost", "Planned image cost"],
            ["video_cost", "Planned video cost"],
          ] as const
        ).map(([key, label]) => (
          <Field
            key={key}
            label={`${label}${suffix}`}
            type="number"
            placeholder="Unset / unknown"
            value={value[key] ?? ""}
            onChange={(v) =>
              onChange({ ...value, [key]: v === "" ? null : Number(v) })
            }
          />
        ))}
        <Field
          label={`Cost evidence${suffix}`}
          multiline
          value={value.cost_evidence}
          onChange={(cost_evidence) => onChange({ ...value, cost_evidence })}
        />
        <Field
          label={`Maximum quality retries${suffix}`}
          type="number"
          value={value.retry_limit}
          onChange={(v) => onChange({ ...value, retry_limit: Number(v) })}
        />
      </div>
      <label className="fs-policy">
        <input
          type="checkbox"
          checked={value.auto_retry}
          onChange={(e) => onChange({ ...value, auto_retry: e.target.checked })}
        />
        Retry inspected defects automatically{suffix}
      </label>
      <p className="fs-hint">
        Retries require a recorded inspection with a failed criterion or named
        defect. Existing takes stay available. A hard budget requires known
        costs and evidence; unknown exposure can block generation.
      </p>
    </>
  );
}

function BatchControls({
  batch,
  projects,
  busy,
  mode,
  run,
}: {
  batch: Batch;
  projects: ProjectSummary[];
  busy: boolean;
  mode: ControlMode;
  run: Run;
}) {
  const saved = useMemo(() => policyFrom(batch), [batch]);
  const form = useDraft(saved, batch.revision, `batch-policy:${batch.id}`);
  const [sourceId, setSourceId] = useState(
    batch.identity_source_project_id || "",
  );
  const [policyError, setPolicyError] = useState("");
  const source = projects.find((p) => p.id === sourceId);
  const suffix = ` · ${batch.name}`;
  return (
    <article className="q-batch">
      <div className="q-section-heading">
        <div>
          <h3>{batch.name}</h3>
          <p>
            {batch.project_ids.length} {batch.kind} ·{" "}
            {batch.paused
              ? "Paused"
              : `${batch.max_parallel} projects in parallel`}
          </p>
        </div>
        <button
          className="fs-button"
          disabled={busy}
          aria-label={`${batch.paused ? "Resume" : "Pause"} batch${suffix}`}
          onClick={() =>
            run(
              "update_batch",
              {
                batch_id: batch.id,
                policy: { paused: !batch.paused },
                expected_revision: batch.revision,
              },
              batch.paused ? "Batch resumed" : "Batch paused",
            )
          }
        >
          {batch.paused ? "Resume batch" : "Pause batch"}
        </button>
      </div>
      <p className="q-cost">
        {batch.reserved_or_spent} {batch.unit} reserved or spent ·{" "}
        {batch.unknown_cost_jobs} unknown cost
        {batch.unknown_cost_jobs === 1 ? "" : "s"} ·{" "}
        {batch.budget_limit === null
          ? "No batch budget set"
          : `${batch.budget_limit} ${batch.unit} batch budget`}
      </p>
      <p className="fs-hint">
        Shared identity v{batch.identity_version}
        {batch.identity_source_project_id
          ? ` · ${projects.find((p) => p.id === batch.identity_source_project_id)?.name || batch.identity_source_project_id}`
          : " · No canonical source"}{" "}
        ·{" "}
        {batch.auto_retry
          ? `Up to ${batch.retry_limit} inspected quality retries`
          : "Automatic quality retries off"}
      </p>
      <DraftNotice {...form} />
      {policyError && (
        <p role="alert" className="q-error">
          {policyError}
        </p>
      )}
      <details className="q-details" open={mode === "professional"}>
        <summary>Batch policy & shared identity</summary>
        <PolicyFields
          value={form.draft}
          suffix={suffix}
          onChange={(p) => {
            form.edit(() => p);
            setPolicyError("");
          }}
        />
        <button
          className="fs-button"
          aria-label={`Apply batch policy${suffix}`}
          disabled={busy || !form.dirty || form.conflict}
          onClick={async () => {
            try {
              if (
                await run(
                  "update_batch",
                  {
                    batch_id: batch.id,
                    policy: checkedPolicy(form.draft),
                    expected_revision: form.revision,
                  },
                  "Batch policy applied",
                )
              )
                form.saved();
            } catch (e) {
              setPolicyError((e as Error).message);
            }
          }}
        >
          Apply batch policy
        </button>
        <label className="fs-label">
          Identity source{suffix}
          <select
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
          >
            <option value="">
              Choose a project with identity and references
            </option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <p className="fs-hint">
          Sync copies the source’s real canonical reference files and entity
          definitions into every item. It reopens affected work and preserves
          other outputs.
        </p>
        <button
          className="fs-button"
          aria-label={`Sync shared identity${suffix}`}
          disabled={busy || !source || !Number.isInteger(source.revision)}
          onClick={() =>
            source &&
            run(
              "sync_batch_identity",
              {
                batch_id: batch.id,
                source_project_id: source.id,
                expected_revision: batch.revision,
                source_revision: source.revision,
              },
              "Shared identity synchronized",
            )
          }
        >
          Sync shared identity
        </button>
      </details>
    </article>
  );
}

function QueueRow({
  item,
  busy,
  onSelect,
  run,
}: {
  item: QueueItem;
  busy: boolean;
  onSelect: (id: string) => void;
  run: Run;
}) {
  const saved = useMemo(() => ({ priority: item.priority }), [item.priority]);
  const form = useDraft(
    saved,
    item.revision,
    `queue-priority:${item.project_id}`,
  );
  const paused = item.dispatch_paused ?? item.state === "paused";
  const [priorityError, setPriorityError] = useState("");
  const suffix = ` · ${item.project_name}`;
  return (
    <article className="q-row" data-project-id={item.project_id}>
      <div className="q-row-main">
        <div className="q-section-heading">
          <h3>{item.project_name}</h3>
          <span className={`q-state q-state-${item.state}`}>
            {stateLabels[item.state] || item.state.replaceAll("_", " ")}
          </span>
        </div>
        <p className="q-next">{item.message || item.next_action.message}</p>
        <small>
          Next: {item.next_action.action.replaceAll("_", " ")}
          {item.next_action.step
            ? ` · ${item.next_action.step.replaceAll("_", " ")}`
            : ""}{" "}
          · Identity v{item.identity_version} · {item.quality_retries} quality
          retries
        </small>
        {item.lease && (
          <p className="fs-hint">
            Worker {item.lease.actor} · lease expires{" "}
            {new Date(item.lease.expires_at).toLocaleString()}
          </p>
        )}
        <p className="q-cost">
          {item.reserved_or_spent} {item.unit} reserved or spent ·{" "}
          {item.unknown_cost_jobs} unknown cost
          {item.unknown_cost_jobs === 1 ? "" : "s"} · {item.active_jobs} active
          output jobs · {item.failures} failed / interrupted
        </p>
      </div>
      <div className="q-row-actions">
        <button
          className="fs-button"
          aria-label={`Open project${suffix}`}
          onClick={() => onSelect(item.project_id)}
        >
          Open project
        </button>
        <button
          className="fs-link"
          disabled={busy}
          aria-label={`${paused ? "Resume" : "Pause"} project${suffix}`}
          onClick={() =>
            run(
              "set_project_dispatch",
              {
                project_id: item.project_id,
                paused: !paused,
                priority: item.priority,
                expected_revision: item.revision,
              },
              paused ? "Project resumed" : "Project paused",
            )
          }
        >
          {paused ? "Resume project" : "Pause project"}
        </button>
        <DraftNotice {...form} />
        {priorityError && <p role="alert">{priorityError}</p>}
        <details className="q-priority">
          <summary>Priority {item.priority}</summary>
          <Field
            label={`Priority${suffix}`}
            type="number"
            value={form.draft.priority}
            onChange={(v) => {
              form.edit(() => ({ priority: Number(v) }));
              setPriorityError("");
            }}
          />
          <button
            className="fs-link"
            aria-label={`Apply priority${suffix}`}
            disabled={busy || !form.dirty || form.conflict}
            onClick={async () => {
              const priority = form.draft.priority;
              if (
                !Number.isInteger(priority) ||
                priority < -100 ||
                priority > 100
              ) {
                setPriorityError(
                  "Priority must be a whole number from -100 to 100.",
                );
                return;
              }
              if (
                await run(
                  "set_project_dispatch",
                  {
                    project_id: item.project_id,
                    paused,
                    priority,
                    expected_revision: form.revision,
                  },
                  "Project priority applied",
                )
              )
                form.saved();
            }}
          >
            Apply priority
          </button>
        </details>
      </div>
    </article>
  );
}

export function QueueWorkspace({
  templates,
  projects,
  onSelect,
  onChanged,
  profiles,
}: {
  profiles?: {image_profiles:{id:string;name:string}[];video_profiles:{id:string;name:string}[]};
  templates: Template[];
  projects: ProjectSummary[];
  onSelect: (id: string) => void;
  onChanged?: () => void | Promise<unknown>;
}) {
  const [outputType,setOutputType]=useState("video");
  const [generators,setGenerators]=useState({image_generator:"",image_model:"",video_generator:"",video_model:""});
  const [mode, setMode] = useControlMode("queue");
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [idea, setIdea] = useState("");
  const [kind, setKind] = useState("episodes");
  const [count, setCount] = useState(5);
  const [template, setTemplate] = useState("ai-film");
  const [briefs, setBriefs] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [policy, setPolicy] = useState(defaultPolicy);
  const [batchFilter, setBatchFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const request = useRef<{ fingerprint: string; id: string } | null>(null);
  const alive = useRef(true);
  const sequence = useRef(0);
  const load = useCallback(async () => {
    const seq = ++sequence.current;
    const data = await api<Queue>("production_queue");
    if (alive.current && seq === sequence.current) setQueue(data);
  }, []);
  useEffect(() => {
    alive.current = true;
    const refresh = () =>
      load().catch((e) => {
        if (alive.current) setError((e as Error).message);
      });
    void refresh();
    const timer = window.setInterval(() => {
      if (!window.document.hidden) void refresh();
    }, 4000);
    return () => {
      alive.current = false;
      window.clearInterval(timer);
    };
  }, [load]);
  const run: Run = async (operation, args, message) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(operation, args);
      await load();
      await onChanged?.();
      if (alive.current) setNotice(message);
      return true;
    } catch (e) {
      if (alive.current) setError((e as Error).message);
      return false;
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const selectedTemplate = templates.some((t) => t.id === template)
    ? template
    : templates[0]?.id || "";
  const source = projects.find((p) => p.id === sourceId);
  const rows =
    queue?.items.filter(
      (item) =>
        (!batchFilter || item.batch_id === batchFilter) &&
        (!stateFilter || item.state === stateFilter),
    ) || [];
  const agentInstructions = `${queue?.instructions || "Connect your agent to the local Studio MCP server."}\n\nCall claim_queue_task with a unique request_id${batchFilter ? `, batch_id=${batchFilter}` : ""}. Read the returned next_action and get_project. Prepare actual planning outputs; use claim_generation and return real files. Record actual media inspections. Call renew_queue_task(task_id) before the lease expires. Call finish_queue_task(task_id, status='done') after real progress, or status='blocked' with the actual reason. Wait when idle; human approvals belong to the user.`;
  return (
    <section className="q-workspace">
      <div className="fs-eyebrow">IDEA TO PRODUCTION</div>
      <h1>Production queue</h1>
      <p className="fs-lead">
        Start a batch from one idea. Your connected agent develops each item and
        returns real work for review.
      </p>
      <ControlModeSwitch
        mode={mode}
        onChange={setMode}
        label="Production queue"
      />
      {error && (
        <p className="fs-alert" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="fs-toast" role="status">
          {notice}
        </p>
      )}
      <form
        className="q-launch"
        onSubmit={async (event) => {
          event.preventDefault();
          setError("");
          try {
            if (!idea.trim())
              throw new Error("Enter your idea to start a batch.");
            if (!Number.isInteger(count) || count < 1 || count > 100)
              throw new Error("Choose a whole number from 1 to 100 items.");
            const itemBriefs = briefs.trim()
              ? briefs.split("\n").map((b) => b.trim())
              : undefined;
            if (itemBriefs && itemBriefs.length !== count)
              throw new Error(
                "Provide exactly one brief per item, or leave the briefs blank.",
              );
            if (sourceId && (!source || !Number.isInteger(source.revision)))
              throw new Error(
                "Refresh the identity source before creating this batch.",
              );
            if(!generators.image_generator || !generators.image_model.trim() || (outputType==="video" && (!generators.video_generator || !generators.video_model.trim()))) throw new Error("Choose generator profiles and enter model names before creating a batch.");
            const args = {
              output_type:outputType,
              settings:generatorSettings(outputType,generators),
              name: name.trim() || idea.trim().split("\n")[0].slice(0, 100),
              idea: idea.trim(),
              kind,
              template_id: selectedTemplate,
              count,
              policy: checkedPolicy(policy),
              ...(itemBriefs ? { briefs: itemBriefs } : {}),
              ...(source
                ? {
                    identity_source_project_id: source.id,
                    source_revision: source.revision,
                  }
                : {}),
            };
            const fingerprint = JSON.stringify(args);
            if (request.current?.fingerprint !== fingerprint)
              request.current = { fingerprint, id: crypto.randomUUID() };
            if (
              await run(
                "create_batch",
                { ...args, request_id: request.current.id },
                `${count} projects created. Connect an agent to start the next available work.`,
              )
            ) {
              setName("");
              setIdea("");
              setBriefs("");
              request.current = null;
            }
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <h2>Start from an idea</h2>
        <label className="fs-label">Output type<select value={outputType} onChange={e=>setOutputType(e.target.value)}><option value="image">Image</option><option value="video">Video</option></select></label>
        {["image",...(outputType==="video"?["video"]:[])].map(kind=><div key={kind}><label className="fs-label">{kind==="image"?"Image":"Video"} generator profile<select value={generators[`${kind}_generator` as keyof typeof generators]} onChange={e=>setGenerators({...generators,[`${kind}_generator`]:e.target.value})}><option value="">Choose a profile</option>{(kind==="image"?profiles?.image_profiles:profiles?.video_profiles)?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><Field label={`${kind==="image"?"Image":"Video"} model name`} value={generators[`${kind}_model` as keyof typeof generators]} onChange={v=>setGenerators({...generators,[`${kind}_model`]:v})}/></div>)}
        <Field
          label="Batch name"
          value={name}
          onChange={setName}
          placeholder="Optional � use the first words of your idea"
        />
        <Field
          label="Idea"
          multiline
          value={idea}
          onChange={setIdea}
          placeholder="What should this batch explore or produce?"
        />
        <div className="cv-form-grid">
          <label className="fs-label">
            Template recipe
            <select
              value={selectedTemplate}
              onChange={(e) => setTemplate(e.target.value)}
            >
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.saved ? " · saved recipe" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="fs-label">
            Batch kind
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="episodes">Episodes</option>
              <option value="variations">Variations</option>
              <option value="campaign">Campaign</option>
            </select>
          </label>
          <Field
            label="Number of items"
            type="number"
            value={count}
            onChange={(v) => setCount(Number(v))}
          />
        </div>
        <ModeDetail mode={mode}>
          <Field
            label="Per-item briefs (one per line)"
            multiline
            value={briefs}
            onChange={setBriefs}
          />
        </ModeDetail>
        <details className="q-details" open={mode === "professional"}>
          <summary>Batch limits, quality & shared identity</summary>
          <PolicyFields value={policy} onChange={setPolicy} />
          <label className="fs-label">
            Canonical identity source
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              <option value="">Independent identities</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <p className="fs-hint">
            Optional: copy this project’s canonical entities and actual
            reference files into each item. Inspect generated media to verify
            consistency.
          </p>
        </details>
        <div className="q-launch-footer">
          <p className="fs-hint">
            1–100 independent projects. The idea starts planning; it is not a
            completed script or generated media.
          </p>
          <button
            type="submit"
            className="fs-primary"
            disabled={busy || !selectedTemplate}
          >
            Create production batch
          </button>
        </div>
      </form>
      <div className="q-section-heading q-queue-heading">
        <div>
          <h2>Live workload</h2>
          <p>Updates every 4 seconds while this workspace is visible.</p>
        </div>
        <button
          className="fs-button"
          disabled={busy}
          onClick={() => load().catch((e) => setError((e as Error).message))}
        >
          Refresh queue
        </button>
      </div>
      <div className="q-filters">
        <label className="fs-label">
          Batch filter
          <select
            value={batchFilter}
            onChange={(e) => setBatchFilter(e.target.value)}
          >
            <option value="">All projects</option>
            {queue?.batches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <label className="fs-label">
          Queue state
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
          >
            <option value="">All states</option>
            {Object.entries(stateLabels).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!queue ? (
        <p className="fs-body" role="status">
          Loading production queue…
        </p>
      ) : (
        <>
          {queue.batches
            .filter((b) => !batchFilter || b.id === batchFilter)
            .map((b) => (
              <BatchControls
                key={b.id}
                batch={b}
                projects={projects}
                busy={busy}
                mode={mode}
                run={run}
              />
            ))}
          <div className="q-items" aria-label="Production items">
            {rows.map((item) => (
              <QueueRow
                key={item.project_id}
                item={item}
                busy={busy}
                onSelect={onSelect}
                run={run}
              />
            ))}
          </div>
          {!rows.length && (
            <p className="q-empty">
              {queue.items.length
                ? "No projects match these filters."
                : "No production work yet. Start a batch above or create an individual project."}
            </p>
          )}
        </>
      )}
      <details className="q-agent q-details">
        <summary>Give your agent the queue</summary>
        <Field
          label="Agent queue instructions"
          multiline
          readOnly
          value={agentInstructions}
          onChange={() => {}}
        />
        <button
          className="fs-button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(agentInstructions);
              setNotice("Agent queue instructions copied");
            } catch {
              setError(
                "Clipboard unavailable. Select and copy the agent instructions above.",
              );
            }
          }}
        >
          Copy agent instructions
        </button>
      </details>
    </section>
  );
}
