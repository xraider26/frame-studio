"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Clapperboard,
  Copy,
  Film,
  Folder,
  Layers,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import "./studio.css";
import { studioApi as api } from "./client";
import { ProjectActions } from "./project-actions";
import { GeneratorExport } from "./generator-export";
import {
  CreativeWorkspace,
  TechniqueLibrary,
  Checks,
} from "./creative-workspace";
import { ProductionWorkspace } from "./production-workspace";
import { QueueWorkspace } from "./queue-workspace";
import { TakesWorkspace } from "./takes-workspace";
import { EditorWorkspace } from "./editor-workspace";
import {
  TemplateWorkspace,
  type TemplateChoice,
  type SavedTemplate,
} from "./template-workspace";
import { RecipeWorkspace } from "./recipe-workspace";
import "./recipes.css";
import type { Project, Job, Action, Catalog } from "./creative-types";
import "./creative.css";
import "./control-mode.css";
import "./queue.css";

type Step = { id: string; name: string };
type Template = TemplateChoice;
type Summary = Pick<Project, "id" | "name" | "template_id" | "revision">;
type Connection = {
  id: string;
  name: string;
  enabled: boolean;
  has_key: boolean;
  base_url: string;
  used_requests: number;
  max_requests: number;
};
type Capabilities = {
  steps: Step[];
  templates: Template[];
  inbox: string;
  connections: Connection[];
  video_profiles: { id: string; name: string; hint: string; source?: string }[];
  image_profiles: { id: string; name: string; hint: string; source?: string }[];
};

const labels: Record<string, string> = {
  draft: "Not started",
  awaiting_review: "Needs your approval",
  approved: "Approved by you",
  auto_proceeded: "Completed automatically",
  awaiting_external_output: "Waiting for agent output",
  running: "API generation running",
  succeeded: "Output received",
  succeeded_stale: "Earlier revision retained",
  superseded: "Prompt changed",
  canceled: "Canceled",
  interrupted: "Interrupted",
  failed: "Failed",
};
const closed = (s: string) => ["approved", "auto_proceeded"].includes(s);
const pretty = (s: string) => labels[s] || s.replaceAll("_", " ");
const nav = [
  { id: "home", label: "Project home", icon: Folder },
  { id: "story", label: "Story & timing", icon: Film },
  { id: "bible", label: "Production bible", icon: Layers },
  { id: "shots", label: "Shots & direction", icon: Clapperboard },
  { id: "knowledge", label: "Techniques & guides", icon: Sparkles },
  { id: "workflow", label: "Workflow & approvals", icon: ShieldCheck },
  { id: "takes", label: "Takes & quality", icon: ShieldCheck },
  { id: "production", label: "Production settings", icon: Settings2 },
  { id: "generator", label: "Generator handoff", icon: Sparkles },
  { id: "handoff", label: "Editor handoff", icon: Layers },
  { id: "connections", label: "Connections & MCP", icon: Link2 },
];

export default function StudioPage() {
  const [mobileMenu, setMobileMenu] = useState(false);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  useEffect(() => {
    api<Catalog>("knowledge_catalog")
      .then(setCatalog)
      .catch((e) => setError(e.message));
  }, []);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [projects, setProjects] = useState<Summary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [view, setView] = useState("queue");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [template, setTemplate] = useState("ai-film");
  const [name, setName] = useState("");
  const [selectedStep, setSelectedStep] = useState("brief");
  const [document, setDocument] = useState("");
  const [documentRevision, setDocumentRevision] = useState(0);
  const [documentDirty, setDocumentDirty] = useState(false);
  const [note, setNote] = useState("");
  const [handoff, setHandoff] = useState<Record<string, unknown> | null>(null);
  const [returnPath, setReturnPath] = useState("");
  const [connectionId, setConnectionId] = useState("");

  const refresh = useCallback(async (id?: string) => {
    const [nextCaps, nextProjects] = await Promise.all([
      api<Capabilities>("studio_capabilities"),
      api<Summary[]>("list_projects"),
    ]);
    setCaps(nextCaps);
    setProjects(nextProjects);
    if (id) setProject(await api<Project>("get_project", { project_id: id }));
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (!window.document.hidden && !busy)
        refresh(project?.id).catch((e) => setError(e.message));
    }, 4000);
    return () => clearInterval(timer);
  }, [refresh, project?.id, busy]);

  useEffect(() => {
    if (project && !documentDirty) {
      setDocument(project.documents[selectedStep]?.text || "");
      setDocumentRevision(project.revision);
    }
  }, [project, selectedStep, documentDirty]);

  async function act(fn: () => Promise<unknown>, message = "Saved") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh(project?.id);
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
      if (project) await refresh(project.id).catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  async function selectProject(id: string) {
    setError("");
    setHandoff(null);
    setReturnPath("");
    setView("home");
    try {
      setProject(await api<Project>("get_project", { project_id: id }));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function create() {
    setBusy(true);
    setError("");
    try {
      const p = await api<Project>("create_project", {
        name,
        template_id: template,
        request_id: crypto.randomUUID(),
      });
      await refresh(p.id);
      setCreating(false);
      setName("");
      setView("home");
      setNotice("Project saved. Your agent can now see it through MCP.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openStep(step: string) {
    setSelectedStep(step);
    setDocument(project?.documents[step]?.text || "");
    setDocumentRevision(project?.revision || 0);
    setDocumentDirty(false);
    setView("workflow");
    setNote("");
  }
  async function claim() {
    if (!project) return;
    await act(async () => {
      const res = await api<{
        handoff?: Record<string, unknown>;
        job?: Job;
        next_action?: Action;
      }>("claim_generation", {
        project_id: project.id,
        request_id: crypto.randomUUID(),
      });
      if (!res.handoff)
        throw new Error(
          res.next_action?.message || "Prepare the earlier steps first.",
        );
      setHandoff(res.handoff);
    }, "Generation handoff ready. Return a real output to continue.");
  }
  const next = project?.next_action;
  const completed = project
    ? Object.values(project.steps).filter((s) => closed(s.status)).length
    : 0;
  const activeJob = project?.jobs.findLast(
    (j) => j.status === "awaiting_external_output" || j.status === "running",
  );
  const handoffJob = project?.jobs.find((j) => j.id === handoff?.job_id);
  const displayedHandoff =
    handoffJob &&
    ["awaiting_external_output", "running"].includes(handoffJob.status)
      ? handoff
      : activeJob?.handoff;
  const currentName =
    caps?.steps.find((s) => s.id === next?.step)?.name || "Project complete";

  return (
    <div className="fs-app">
      <header className="fs-top">
        <a href="/studio" className="fs-brand">
          <span className="fs-mark">▰</span> frame <small>STUDIO</small>
        </a>
        <span className="fs-connection">
          <i />
          {caps ? "Local studio connected" : "Connecting to studio"}
        </span>
        <span className="fs-local">LOCAL WORKSPACE</span>
        <button
          className="fs-mobile-menu"
          aria-expanded={mobileMenu}
          aria-controls="studio-navigation"
          onClick={() => setMobileMenu((v) => !v)}
        >
          <Layers size={14} />
          {mobileMenu ? "Close navigation" : "Studio menu"}
        </button>
      </header>
      <div className="fs-shell">
        <aside
          id="studio-navigation"
          className={`fs-sidebar ${mobileMenu ? "fs-mobile-expanded" : ""}`}
        >
          <div className="fs-eyebrow">WORKSPACE</div>
          <label className="fs-label" htmlFor="project-select">
            Project
          </label>
          <select
            id="project-select"
            value={project?.id || ""}
            onChange={(e) => selectProject(e.target.value)}
          >
            <option value="" disabled>
              Choose a project
            </option>
            {projects.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            className="fs-button fs-new"
            onClick={() => setCreating(true)}
            disabled={!caps}
          >
            <Plus size={14} /> New project
          </button>
          <ProjectActions
            project={project}
            onSelect={async (id) => {
              await refresh();
              await selectProject(id);
            }}
            onRemoved={async () => {
              setProject(null);
              setView("templates");
              await refresh();
            }}
          />
          <button
            className={`fs-nav ${view === "queue" ? "active" : ""}`}
            onClick={() => { setView("queue"); setMobileMenu(false); }}
          >
            <Layers size={16} /> Production queue
          </button>
          <button
            className={`fs-nav ${view === "templates" ? "active" : ""}`}
            onClick={() => setView("templates")}
          >
            <Film size={16} /> Template library
          </button>
          <div className="fs-eyebrow fs-nav-heading">THIS PROJECT</div>
          {nav.map((n) => (
            <button
              key={n.id}
              className={`fs-nav ${view === n.id ? "active" : ""}`}
              disabled={!project && n.id !== "connections"}
              onClick={() => {
                setMobileMenu(false);
                setView(n.id);
                if (n.id === "workflow") openStep(next?.step || "brief");
              }}
            >
              <n.icon size={16} />
              {n.label}
            </button>
          ))}
          <div className="fs-sidebar-bottom">
            <div className="fs-eyebrow">YOUR AGENT. YOUR WORKFLOW.</div>
            <p>
              Plan here. Generate with connected tools. Edit in your own
              software.
            </p>
            <a href="/">
              Companion dashboard <ArrowRight size={12} />
            </a>
          </div>
        </aside>
        <main className="fs-main">
          {error && (
            <div className="fs-alert" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {notice && (
            <div className="fs-toast" role="status">
              <Check size={14} />
              {notice}
            </div>
          )}
          <div className="fs-breadcrumb">
            Workspace <ChevronRight size={12} />
            {project?.name || "Start a project"} <ChevronRight size={12} />
            {view === "queue" ? "Production queue" : nav.find((n) => n.id === view)?.label || "Template library"}
            <button
              aria-label="Refresh studio"
              onClick={() =>
                refresh(project?.id).catch((e) => setError(e.message))
              }
            >
              <RefreshCw size={14} />
            </button>
          </div>

          {view === "queue" && (
            <QueueWorkspace templates={caps?.templates || []} projects={projects}
              onSelect={selectProject} onChanged={() => refresh(project?.id)} />
          )}

          {((!project && !["connections", "queue"].includes(view)) || view === "templates") && (
            <section className="fs-library">
              <div className="fs-eyebrow">TEMPLATE LIBRARY</div>
              <h1>Your reusable setups.</h1>
              <p className="fs-lead">
                Choose a production recipe, inspect its examples, or reuse your own setup.
              </p>
              <RecipeWorkspace project={project} busy={busy} save={(fn)=>act(fn,"Recipe updated")} onNew={(id)=>{setTemplate(id);setCreating(true);}} />
              <TemplateWorkspace
                project={project}
                templates={(caps?.templates || []).filter(
                  (t): t is SavedTemplate => !!t.saved,
                )}
                busy={busy}
                save={(fn) => act(fn, "Template saved")}
                onNew={(id) => {
                  setTemplate(id);
                  setCreating(true);
                }}
              />
              {!caps && (
                <button
                  className="fs-button"
                  onClick={() => refresh().catch((e) => setError(e.message))}
                >
                  Retry connection
                </button>
              )}
            </section>
          )}

          {project && view === "home" && (
            <section>
              <div className="fs-heading">
                <div>
                  <div className="fs-eyebrow">
                    {caps?.templates
                      .find((t) => t.id === project.template_id)
                      ?.name.toUpperCase()}{" "}
                    / PROJECT HOME
                  </div>
                  <h1>{project.name}</h1>
                  <p className="fs-subtitle">
                    {project.settings.platform} ·{" "}
                    {project.settings.duration_seconds}s target ·{" "}
                    {project.settings.aspect_ratio}
                  </p>
                </div>
                <div className="cv-template-actions">
                  <button
                    className="fs-button"
                    onClick={() => setView("templates")}
                  >
                    Save as template
                  </button>
                  <span className="fs-badge">
                    {next?.action === "await_approval"
                      ? "Your approval needed"
                      : currentName}
                  </span>
                </div>
              </div>
              <div className="fs-next">
                <div>
                  <div className="fs-eyebrow">YOUR NEXT STEP</div>
                  <h2>{next?.message}</h2>
                  <p>
                    {next?.action === "await_approval"
                      ? "Review the current revision before your agent continues."
                      : "The same saved step is available to your agent through MCP."}
                  </p>
                </div>
                <button
                  className="fs-primary"
                  onClick={() => openStep(next?.step || "final_review")}
                >
                  {next?.action === "await_approval"
                    ? "Review step"
                    : "Open workflow"}{" "}
                  <ArrowRight size={15} />
                </button>
              </div>
              <div className="fs-home-columns">
                <div>
                  <div className="fs-eyebrow">
                    {completed} OF {caps?.steps.length || 7} STEPS COMPLETE
                  </div>
                  <div className="fs-step-list">
                    {caps?.steps.map((s, i) => (
                      <button
                        className={`fs-step ${next?.step === s.id ? "current" : ""}`}
                        key={s.id}
                        onClick={() => openStep(s.id)}
                      >
                        <span
                          className={`fs-step-index ${closed(project.steps[s.id].status) ? "done" : ""}`}
                        >
                          {closed(project.steps[s.id].status) ? (
                            <Check size={14} />
                          ) : (
                            i + 1
                          )}
                        </span>
                        <div>
                          <strong>{s.name}</strong>
                          <small>{pretty(project.steps[s.id].status)}</small>
                        </div>
                        <span className="fs-step-policy">
                          {project.approval_policy[s.id] ? "Review" : "Auto"}
                        </span>
                        <ChevronRight size={14} />
                      </button>
                    ))}
                  </div>
                  <button
                    className="fs-button"
                    onClick={() => setView("shots")}
                  >
                    Edit shots & direction <ArrowRight size={14} />
                  </button>
                </div>
                <div className="fs-inspector">
                  <h3>Project at a glance</h3>
                  {[
                    [
                      "Template",
                      caps?.templates.find((t) => t.id === project.template_id)
                        ?.name,
                    ],
                    ["Format", project.settings.aspect_ratio],
                    ["Planned shots", project.shots.length],
                    [
                      "Returned media",
                      project.assets.filter((a) => !a.stale && !a.role).length,
                    ],
                    ["Revision", project.revision],
                  ].map(([label, value]) => (
                    <div className="fs-fact" key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                  <div className="fs-eyebrow fs-section-label">
                    RECENT ACTIVITY
                  </div>
                  <div className="fs-activity">
                    {project.history
                      .slice(-5)
                      .reverse()
                      .map((e, i) => (
                        <p key={i}>
                          <span>{e.message}</span>
                          <small>
                            {e.actor} ·{" "}
                            {new Date(e.at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </small>
                        </p>
                      ))}
                  </div>
                </div>
              </div>
            </section>
          )}

          {project && view === "workflow" && (
            <section>
              <div className="fs-heading">
                <div>
                  <div className="fs-eyebrow">
                    WORKFLOW / REVISION {project.revision}
                  </div>
                  <h1>You choose where it pauses.</h1>
                  <p className="fs-lead">
                    Tick a step to require your approval. Unticked steps proceed
                    when their required outputs are ready.
                  </p>
                </div>
              </div>
              <div className="fs-workflow">
                <div className="fs-stage-nav">
                  {caps?.steps.map((s, i) => (
                    <div
                      key={s.id}
                      className={`fs-stage-row ${selectedStep === s.id ? "selected" : ""}`}
                    >
                      <button onClick={() => openStep(s.id)}>
                        <span>{String(i + 1).padStart(2, "0")}</span>
                        <div>
                          <strong>{s.name}</strong>
                          <small>{pretty(project.steps[s.id].status)}</small>
                        </div>
                      </button>
                      <label className="fs-policy">
                        <input
                          type="checkbox"
                          aria-label={`Approval required for ${s.name}`}
                          checked={project.approval_policy[s.id]}
                          disabled={busy}
                          onChange={(e) =>
                            act(
                              () =>
                                api("set_policy", {
                                  project_id: project.id,
                                  expected_revision: project.revision,
                                  policy: { [s.id]: e.target.checked },
                                }),
                              "Approval policy saved",
                            )
                          }
                        />
                        <span>Approval required</span>
                      </label>
                    </div>
                  ))}
                </div>
                <div className="fs-stage-content">
                  <div className="fs-eyebrow">
                    {caps?.steps
                      .find((s) => s.id === selectedStep)
                      ?.name.toUpperCase()}
                  </div>
                  <h2>
                    {pretty(project.steps[selectedStep]?.status || "draft")}
                  </h2>
                  {["brief", "script", "editor_handoff"].includes(
                    selectedStep,
                  ) && (
                    <>
                      <label className="fs-label" htmlFor="step-document">
                        {selectedStep === "editor_handoff"
                          ? "Editing notes & handoff"
                          : "Step document"}
                      </label>
                      <textarea
                        id="step-document"
                        rows={10}
                        value={document}
                        onChange={(e) => {
                          setDocument(e.target.value);
                          setDocumentDirty(true);
                        }}
                        placeholder={
                          selectedStep === "brief"
                            ? "Who is this for? What should they feel or do? What is the story?"
                            : selectedStep === "script"
                              ? "Write the actual script, dialogue and story beats…"
                              : "Record editing notes and the handoff to your preferred editor…"
                        }
                      />
                      <button
                        className="fs-primary"
                        disabled={busy || !document.trim()}
                        onClick={() =>
                          act(
                            () =>
                              api("complete_step", {
                                project_id: project.id,
                                expected_revision: documentRevision,
                                step: selectedStep,
                                output: { text: document },
                              }).then(() => {
                                setDocumentDirty(false);
                              }),
                            "Step prepared",
                          )
                        }
                      >
                        Save & complete step <ArrowRight size={14} />
                      </button>
                    </>
                  )}
                  {["visual_direction", "pilot", "production"].includes(
                    selectedStep,
                  ) && (
                    <>
                      <p className="fs-body">
                        {selectedStep === "visual_direction"
                          ? "Return one keyframe for each planned shot. The studio keeps the prompts, references and takes together."
                          : selectedStep === "pilot"
                            ? "Generate the first shot as a pilot. Check its motion and sound before producing the remaining shots."
                            : "Continue through the remaining shots using the approved direction and pilot."}
                      </p>
                      <button
                        className="fs-button"
                        onClick={() => setView("shots")}
                      >
                        Open shots & prompts <ArrowRight size={14} />
                      </button>
                      <div className="fs-media-strip">
                        {project.assets
                          .filter((a) => !a.stale && !a.role)
                          .slice(-3)
                          .map((a) =>
                            a.kind === "image" ? (
                              <img
                                key={a.id}
                                src={a.url}
                                alt="Returned generation"
                              />
                            ) : (
                              <video
                                key={a.id}
                                src={a.url}
                                controls
                                preload="metadata"
                              />
                            ),
                          )}
                      </div>
                    </>
                  )}
                  {selectedStep === "final_review" && (
                    <>
                      <p className="fs-body">
                        Import the actual MP4 you assembled in your own editor.
                      </p>
                      <ImportFile
                        label="Final MP4 path inside studio inbox"
                        busy={busy}
                        onImport={(path) =>
                          act(
                            () =>
                              api("import_final", {
                                project_id: project.id,
                                path,
                                expected_revision: project.revision,
                              }),
                            "External edit returned",
                          )
                        }
                      />
                      {project.assets
                        .filter((a) => a.kind === "final_video" && !a.stale)
                        .map((a) => (
                          <video
                            className="fs-final-video"
                            key={a.id}
                            src={a.url}
                            controls
                          />
                        ))}
                    </>
                  )}
                  {project.next_action.action === "await_approval" &&
                    project.next_action.step === selectedStep && (
                      <div className="fs-review">
                        <div className="fs-eyebrow">YOUR QUALITY CHECK</div>
                        <p>
                          Review the current document or media, then approve or
                          request changes.
                        </p>
                        <textarea
                          rows={3}
                          aria-label="Review notes"
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          placeholder="Feedback for the next pass…"
                        />
                        <div className="fs-actions">
                          <button
                            className="fs-primary"
                            disabled={busy || documentDirty}
                            onClick={() =>
                              act(
                                () =>
                                  api("review", {
                                    project_id: project.id,
                                    step: selectedStep,
                                    approve: true,
                                    note,
                                    expected_revision: documentRevision,
                                  }),
                                "Approved. Your agent can continue.",
                              )
                            }
                          >
                            Approve this step <Check size={14} />
                          </button>
                          <button
                            className="fs-button"
                            disabled={busy || documentDirty || !note.trim()}
                            onClick={() =>
                              act(
                                () =>
                                  api("review", {
                                    project_id: project.id,
                                    step: selectedStep,
                                    approve: false,
                                    note,
                                    expected_revision: documentRevision,
                                  }),
                                "Changes requested",
                              )
                            }
                          >
                            Request changes
                          </button>
                        </div>
                      </div>
                    )}
                  {next?.action === "record_quality" && (
                    <div className="cv-section">
                      <p className="fs-body">{next.message}</p>
                      <button
                        className="fs-primary"
                        onClick={() => setView("takes")}
                      >
                        Inspect takes & record quality
                      </button>
                    </div>
                  )}
                  {next?.action === "resolve_resources" && (
                    <div className="cv-section">
                      <p className="fs-body">{next.message}</p>
                      <button
                        className="fs-button"
                        onClick={() => setView("production")}
                      >
                        Review production resources
                      </button>
                    </div>
                  )}
                  {next?.action === "resolve_preflight" && (
                    <>
                      <Checks
                        checks={project.preflight}
                        shots={project.shots}
                      />
                      <button
                        className="fs-button"
                        onClick={() => setView("shots")}
                      >
                        Resolve shot direction
                      </button>
                    </>
                  )}
                  {next?.action === "generate" &&
                    next.step === selectedStep && (
                      <div className="fs-generation">
                        <button
                          className="fs-primary"
                          disabled={busy}
                          onClick={claim}
                        >
                          Prepare generation handoff <ArrowRight size={14} />
                        </button>
                        <p className="fs-hint">
                          Your agent gets the same handoff with MCP. Creating it
                          does not start a paid generation.
                        </p>
                      </div>
                    )}
                  {displayedHandoff && (
                    <div className="fs-handoff-box">
                      <div className="fs-eyebrow">GENERATION HANDOFF</div>
                      <JsonBrief data={displayedHandoff} />
                      <label className="fs-label" htmlFor="return-path">
                        Returned output path
                      </label>
                      <input
                        id="return-path"
                        value={returnPath}
                        onChange={(e) => setReturnPath(e.target.value)}
                        placeholder={`${caps?.inbox}\\result.png`}
                      />
                      <button
                        className="fs-button"
                        disabled={busy || !returnPath}
                        onClick={() =>
                          act(
                            () =>
                              api("return_generation", {
                                job_id: displayedHandoff.job_id,
                                output_path: returnPath,
                              }),
                            "Real media returned to the studio",
                          )
                        }
                      >
                        Attach returned generation
                      </button>
                      <div className="fs-api-run">
                        <label className="fs-label" htmlFor="executor-select">
                          Or execute through a connected API
                        </label>
                        <select
                          id="executor-select"
                          value={connectionId}
                          onChange={(e) => setConnectionId(e.target.value)}
                        >
                          <option value="">Choose an enabled connection</option>
                          {caps?.connections
                            .filter((c) => c.enabled)
                            .map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                        </select>
                        <button
                          className="fs-button"
                          disabled={
                            busy ||
                            !connectionId ||
                            activeJob?.status === "running" ||
                            next?.action !== "generate" ||
                            next?.shot_id !== displayedHandoff.shot_id
                          }
                          onClick={() =>
                            act(
                              () =>
                                api("run_provider", {
                                  job_id: displayedHandoff.job_id,
                                  connection_id: connectionId,
                                }),
                              "API job submitted. Progress is saved.",
                            )
                          }
                        >
                          Generate via API
                        </button>
                        <small>
                          Uses the provider’s billing and your connection
                          request limit.
                        </small>
                      </div>
                    </div>
                  )}
                  {project.jobs.length > 0 && (
                    <div className="fs-jobs">
                      <div className="fs-eyebrow">GENERATION JOBS</div>
                      {project.jobs
                        .slice(-5)
                        .reverse()
                        .map((j) => (
                          <div className="fs-job" key={j.id}>
                            <strong>
                              {project.shots.find((s) => s.id === j.shot_id)
                                ?.title || "Earlier shot"}{" "}
                              · {j.kind}
                            </strong>
                            <span>{pretty(j.status)}</span>
                            {j.error && <p>{j.error}</p>}
                            {j.status === "awaiting_external_output" && (
                              <button
                                className="fs-link"
                                onClick={() =>
                                  act(
                                    () => api("cancel_job", { job_id: j.id }),
                                    "Handoff canceled",
                                  )
                                }
                              >
                                Cancel handoff
                              </button>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

          {project && view === "shots" && (
            <CreativeWorkspace
              key={project.id}
              project={project}
              catalog={catalog}
              busy={busy}
              inbox={caps?.inbox || ""}
              save={(fn) => act(fn, "Shot direction saved")}
            />
          )}
          {project && ["story", "bible", "production"].includes(view) && (
            <ProductionWorkspace
              key={project.id + view}
              project={project}
              view={view as "story" | "bible" | "production"}
              catalog={catalog}
              busy={busy}
              save={(fn) => act(fn, "Production plan saved")}
            />
          )}
          {view === "knowledge" && <TechniqueLibrary catalog={catalog} />}
          {project && view === "takes" && (
            <TakesWorkspace
              key={project.id}
              project={project}
              busy={busy}
              save={(fn) => act(fn, "Production evidence saved")}
            />
          )}
          {project && view === "generator" && caps && (
            <GeneratorExport
              key={project.id}
              project={project}
              videoProfiles={caps.video_profiles}
              imageProfiles={caps.image_profiles}
              busy={busy}
              save={(fn) => act(fn, "Generator choices saved")}
            />
          )}
          {project && view === "handoff" && (
            <EditorWorkspace
              project={project}
              onRecord={() => openStep("editor_handoff")}
            />
          )}
          {view === "connections" && (
            <Connections
              caps={caps}
              busy={busy}
              save={(fn) => act(fn, "Connection saved")}
            />
          )}
          <footer className="fs-footer">
            <span>
              <i /> Real local project storage
            </span>
            <span>Generation: agent tools or configured API</span>
            <span>
              {project
                ? `Revision ${project.revision} saved`
                : "Choose a template to begin"}
            </span>
          </footer>
        </main>
      </div>
      {creating && (
        <div className="fs-modal-backdrop">
          <section
            className="fs-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Create project"
          >
            <button
              className="fs-close"
              aria-label="Close new project"
              onClick={() => setCreating(false)}
            >
              <X size={20} />
            </button>
            <div className="fs-eyebrow">NEW PROJECT</div>
            <h2>Start with a structure.</h2>
            <label className="fs-label" htmlFor="new-name">
              Project name
            </label>
            <input
              id="new-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Give your project a name"
            />
            <label className="fs-label" htmlFor="new-template">
              Content template
            </label>
            <select
              id="new-template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
            >
              {caps?.templates.map((t) => (
                <option value={t.id} key={t.id}>
                  {t.saved ? "Saved · " : ""}
                  {t.name}
                </option>
              ))}
            </select>
            <p className="fs-hint">
              {caps?.templates
                .find((t) => t.id === template)
                ?.structure.join(" → ")}
            </p>
            <button
              className="fs-primary"
              disabled={busy || !name.trim()}
              onClick={create}
            >
              {busy ? (
                <Loader2 size={15} className="fs-spin" />
              ) : (
                <Plus size={15} />
              )}{" "}
              Create project
            </button>
          </section>
        </div>
      )}
    </div>
  );
}

function JsonBrief({ data }: { data: unknown }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="fs-json">
      <textarea
        aria-label="Handoff data"
        readOnly
        value={JSON.stringify(data, null, 2)}
        onFocus={(e) => e.target.select()}
        rows={9}
      />
      <button
        className="fs-button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
            setCopied(true);
          } catch {
            setCopied(false);
          }
        }}
      >
        <Copy size={13} />
        {copied ? "Copied" : "Copy handoff"}
      </button>
      <small>You can also select and copy the text directly.</small>
    </div>
  );
}

function ImportFile({
  label,
  busy,
  onImport,
}: {
  label: string;
  busy: boolean;
  onImport: (path: string) => Promise<void>;
}) {
  const [path, setPath] = useState("");
  return (
    <div className="fs-import">
      <label className="fs-label">
        {label}
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="Absolute path to your local file"
        />
      </label>
      <button
        className="fs-button"
        disabled={busy || !path}
        onClick={() => onImport(path)}
      >
        Import real file
      </button>
    </div>
  );
}

function Connections({
  caps,
  busy,
  save,
}: {
  caps: Capabilities | null;
  busy: boolean;
  save: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [form, setForm] = useState({
    id: "",
    name: "",
    base_url: "",
    api_key: "",
    enabled: false,
    max_requests: 1,
  });
  const [client, setClient] = useState("Cursor / Claude Code");
  const script = "G:/AI/YT/flow-companion-studio/backend/studio_mcp.py";
  const python =
    "G:/AI/YT/flow-companion-studio/backend/.venv/Scripts/python.exe";
  const config =
    client === "Codex"
      ? `[mcp_servers.frame_studio]\ncommand = "${python}"\nargs = ["${script}"]\n\n[mcp_servers.frame_studio.env]\nSTUDIO_CLIENT_NAME = "codex"`
      : JSON.stringify(
          {
            mcpServers: {
              frame_studio: {
                command: python,
                args: [script],
                env: {
                  STUDIO_CLIENT_NAME:
                    client === "Antigravity" ? "antigravity" : "agent",
                },
              },
            },
          },
          null,
          2,
        );
  return (
    <section>
      <div className="fs-eyebrow">CONNECTIONS</div>
      <h1>Your agent runs the workflow.</h1>
      <p className="fs-lead">
        Connect once. Your agent reads the next step, takes a generation
        handoff, and returns the real output.
      </p>
      <div className="fs-connection-flow">
        <span>Agent request</span>
        <ArrowRight size={14} />
        <span>Studio MCP</span>
        <ArrowRight size={14} />
        <span>Generation tools</span>
        <ArrowRight size={14} />
        <span>Returned media</span>
        <ArrowRight size={14} />
        <span>Your review or auto-proceed</span>
      </div>
      <div className="fs-connection-columns">
        <div>
          <h2>Connect your agent</h2>
          <p className="fs-body">
            Start the local studio, then add this server to your client’s MCP
            settings. No generation API key is needed for the agent handoff
            mode.
          </p>
          <label className="fs-label">
            MCP client
            <select value={client} onChange={(e) => setClient(e.target.value)}>
              {[
                "Cursor / Claude Code",
                "Codex",
                "Antigravity",
                "Claude Desktop",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <textarea
            className="fs-config"
            rows={12}
            aria-label="MCP client configuration"
            readOnly
            value={config}
            onFocus={(e) => e.target.select()}
          />
          <p className="fs-hint">
            Setup instructions: <code>docs/MCP.md</code> in the project folder.
            Client configurations are provided, not silently installed.
          </p>
          <h3>Try this in your agent</h3>
          <blockquote>
            “Use Frame Studio to create a short drama. Prepare the brief and
            script, follow the project’s approval policy, then get the next
            generation handoff. Return each real output before continuing.”
          </blockquote>
          <div className="fs-eyebrow fs-section-label">
            LOCAL GENERATION INBOX
          </div>
          <code className="fs-path">
            {caps?.inbox || "Start studio backend to see the inbox"}
          </code>
        </div>
        <div>
          <h2>API generators</h2>
          <p className="fs-body">
            Optional. Connect a generator that implements the studio’s JSON Job
            API contract. Vendor-specific APIs need an adapter.
          </p>
          {caps?.connections.map((c) => (
            <div key={c.id} className="fs-connection-item">
              <div>
                <strong>{c.name}</strong>
                <small>
                  {c.enabled ? "Enabled" : "Disabled"} · {c.used_requests}/
                  {c.max_requests} requests ·{" "}
                  {c.has_key ? "Key saved" : "No key"}
                </small>
              </div>
              <button
                className="fs-link"
                onClick={() =>
                  setForm({
                    id: c.id,
                    name: c.name,
                    base_url: c.base_url,
                    api_key: "",
                    enabled: c.enabled,
                    max_requests: c.max_requests,
                  })
                }
              >
                Edit
              </button>
            </div>
          ))}
          <div className="fs-form-grid fs-single">
            {[
              ["id", "Connection ID", "my-generator"],
              ["name", "Display name", "My image & video generator"],
              ["base_url", "API base URL", "http://127.0.0.1:9000"],
              [
                "api_key",
                "Bearer API key (optional)",
                "Stored on this computer only",
              ],
            ].map(([key, label, placeholder]) => (
              <label className="fs-label" key={key}>
                {label}
                <input
                  type={key === "api_key" ? "password" : "text"}
                  value={form[key as "id" | "name" | "base_url" | "api_key"]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={placeholder}
                  autoComplete="off"
                />
              </label>
            ))}
            <label className="fs-label">
              Maximum submitted requests
              <input
                type="number"
                min={1}
                max={1000}
                value={form.max_requests}
                onChange={(e) =>
                  setForm({ ...form, max_requests: Number(e.target.value) })
                }
              />
            </label>
            <label className="fs-policy">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) =>
                  setForm({ ...form, enabled: e.target.checked })
                }
              />
              <span>Enable generation through this API</span>
            </label>
          </div>
          <button
            className="fs-primary"
            disabled={busy || !form.id || !form.base_url}
            onClick={() =>
              save(async () => {
                await api("save_connection", form);
                setForm({ ...form, api_key: "" });
              })
            }
          >
            Save API connection <Link2 size={14} />
          </button>
          <p className="fs-hint">
            Keys are never returned to the browser or MCP. The request limit
            bounds submissions; it is not a currency budget.
          </p>
          <details>
            <summary>JSON Job API contract</summary>
            <p>
              POST <code>/generate</code> receives the handoff. Return{" "}
              <code>
                {
                  '{"status":"succeeded","output":{"base64":"…","mime_type":"image/png"}}'
                }
              </code>{" "}
              or a <code>queued/running</code> status with a <code>job_id</code>
              . GET <code>/jobs/:id</code> returns the same response format. MP4
              uses <code>video/mp4</code>. URL-only outputs require an adapter.
            </p>
          </details>
        </div>
      </div>
    </section>
  );
}
