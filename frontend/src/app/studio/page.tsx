"use client";
import {generatorSettings} from "./generator-settings";

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
import { mcpConfig, type McpLaunch } from "./mcp-config";
import { ProjectActions } from "./project-actions";
import { MediaUpload } from "./media-upload";
import { CreativeBrief, BriefFields } from "./creative-brief";
import { GeneratorExport } from "./generator-export";
import {
  CreativeWorkspace,
  Checks,
} from "./creative-workspace";
import { ProductionWorkspace } from "./production-workspace";
import { QueueWorkspace } from "./queue-workspace";
import { TakesWorkspace } from "./takes-workspace";
import { EditorWorkspace } from "./editor-workspace";
import type { TemplateChoice } from "./template-workspace";
import { TemplateHub } from "./template-hub";
import { SequenceWorkspace } from "./sequence-workspace";
import { StepDocument } from "./step-document";
import { ImageDelivery } from "./image-delivery";
import { nextActionTarget, projectStages, stageForView, stageTabs, templateForOutput, templatesForOutput, type NavigationTarget } from "./studio-navigation";
import { CinematographyLibrary } from "./cinematography-library";
import "./cinematography.css";
import "./recipes.css";
import type { Project, Job, Action, Catalog } from "./creative-types";
import "./creative.css";
import "./control-mode.css";
import "./queue.css";
import "./template-hub.css";
import "./studio-navigation.css";

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
  mcp_launch?: McpLaunch;
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
  { id: "knowledge", label: "Camera & visual library", icon: Sparkles },
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
  const [outputType,setOutputType]=useState<"image"|"video">("video");
  const [generators,setGenerators]=useState({image_generator:"",image_model:"",video_generator:"",video_model:""});
  const [brief,setBrief]=useState<Record<string,string>>({});
  const [selectedStep, setSelectedStep] = useState("brief");
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
    if (caps) setTemplate(current => templateForOutput(caps.templates, outputType, current));
  }, [caps, outputType]);

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
    setDocumentDirty(false);
    setNote("");
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
        output_type: outputType,
        settings: {...generatorSettings(outputType,generators),creative_intake:brief},
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
  function openStep(step: string, review = false) {
    setSelectedStep(step);
    setDocumentDirty(false);
    setView(review ? "review" : "workflow");
    setMobileMenu(false);
    setNote("");
  }
  function navigate(target: NavigationTarget) {
    if (target.step) openStep(target.step, target.view === "review");
    else if (target.view === "review") openStep(next?.step || selectedStep, true);
    else { setView(target.view); setMobileMenu(false); }
  }
  function startFromTemplate(id: string, kind?: "image" | "video") {
    const choice = caps?.templates.find(t => t.id === id);
    setOutputType(kind || choice?.output_type || "video");
    setTemplate(id);
    setCreating(true);
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
  const imageOnly=project?.output_type === "image";
  const visibleSteps=caps?.steps.filter(s=>!imageOnly || !["pilot","production","editor_handoff"].includes(s.id)).map(s=>({...s,name:imageOnly&&s.id==="script"?"Visual concept":s.name}));
  const next = project?.next_action;
  const stage = stageForView(view, selectedStep);
  const tabs = stage ? stageTabs(stage, imageOnly) : [];
  const selectedTab = tabs.find(t=>t.view===view && (!t.step || t.step===selectedStep));
  const viewLabel = selectedTab?.label || ({queue:"Projects",templates:"Templates",connections:"Connections",production:"Project settings"}[view]) || nav.find(n=>n.id===view)?.label || "Studio";
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
          <span className="fs-mark">◌</span> orchestra <small>STUDIO</small>
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
            aria-current={view === "queue" ? "page" : undefined}
            onClick={() => navigate({view:"queue"})}
          >
            <Folder size={16} /> Projects
          </button>
          <button
            className={`fs-nav ${view === "templates" ? "active" : ""}`}
            aria-current={view === "templates" ? "page" : undefined}
            onClick={() => navigate({view:"templates"})}
          >
            <Layers size={16} /> Templates
          </button>
          <div className="fs-eyebrow fs-nav-heading">THIS PROJECT</div>
          <nav className="fs-project-stages" aria-label="Project stages">
          {projectStages.map((n,i) => (
            <button
              key={n.id}
              className={`fs-nav fs-stage-link ${stage === n.id ? "active" : ""}`}
              aria-current={stage === n.id ? "step" : undefined}
              disabled={!project}
              onClick={() => navigate({view:n.id === "export" && imageOnly ? "delivery" : n.view})}
            >
              <span className="fs-stage-number">{String(i+1).padStart(2,"0")}</span>
              {n.label}
              {stage === n.id && <ChevronRight size={14} />}
            </button>
          ))}
          </nav>
          <div className="fs-sidebar-bottom">
            <button className={`fs-nav ${view === "connections" ? "active" : ""}`} aria-current={view === "connections" ? "page" : undefined} onClick={()=>navigate({view:"connections"})}><Link2 size={16}/> Connections</button>
            <button className={`fs-nav ${view === "production" ? "active" : ""}`} aria-current={view === "production" ? "page" : undefined} disabled={!project} onClick={()=>navigate({view:"production"})}><Settings2 size={16}/> Settings</button>
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
            <span>Studio</span> <ChevronRight size={12} />
            {stage && <><span>{project?.name}</span><ChevronRight size={12}/><span>{projectStages.find(s=>s.id===stage)?.label}</span><ChevronRight size={12}/></>}
            <span aria-current="page">{viewLabel}</span>
            <button
              aria-label="Refresh studio"
              onClick={() =>
                refresh(project?.id).catch((e) => setError(e.message))
              }
            >
              <RefreshCw size={14} />
            </button>
          </div>

          {project && stage && <>
            <div className="fs-task-context">
              <div><span className="fs-eyebrow">{imageOnly ? "IMAGE PROJECT" : "VIDEO PROJECT"} · {project.name}</span><p>{next?.message || "Project complete"}</p></div>
              <button className="fs-primary" onClick={()=>navigate(nextActionTarget(next,project.output_type))}>Continue <ArrowRight size={15}/></button>
            </div>
            <nav className="fs-subnav" aria-label={`${projectStages.find(s=>s.id===stage)?.label} tools`}>
              {tabs.map(t=><button key={t.view+":"+(t.step||"")} className={selectedTab===t?"active":""} aria-current={selectedTab===t?"page":undefined} onClick={()=>navigate(t)}>{t.label}</button>)}
            </nav>
          </>}

          {view === "queue" && (
            <QueueWorkspace profiles={caps || undefined} templates={caps?.templates || []} projects={projects}
              onSelect={selectProject} onChanged={() => refresh(project?.id)} />
          )}

          {((!project && !["connections", "queue", "knowledge"].includes(view)) || view === "templates") && (
            <section className="fs-library">
              <TemplateHub
                project={project}
                choices={caps?.templates || []}
                busy={busy}
                save={(fn) => act(fn, "Template saved")}
                onNew={startFromTemplate}
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
                    {imageOnly ? "Image project" : project.settings.platform} ·{" "}
                    {project.settings.duration_seconds}s target ·{" "}
                    {project.settings.aspect_ratio}
                  </p>
                </div>
                <div className="cv-template-actions">
                  <button
                    className="fs-button"
                    onClick={() => setView("templates")}
                  >
                    Open templates
                  </button>
                  <span className="fs-badge">
                    {next?.action === "await_approval"
                      ? "Your approval needed"
                      : currentName}
                  </span>
                </div>
              </div>
              <CreativeBrief key={project.id} project={project} busy={busy} save={fn=>act(fn,"Creative brief saved")}/>
              <div className="fs-home-columns">
                <div>
                  <div className="fs-eyebrow">
                    {completed} OF {visibleSteps?.length || 7} STEPS COMPLETE
                  </div>
                  <div className="fs-step-list">
                    {visibleSteps?.map((s, i) => (
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

          {project && ["workflow", "review"].includes(view) && (
            <section>
              <div className="fs-heading">
                <div>
                  <div className="fs-eyebrow">
                    WORKFLOW / REVISION {project.revision}
                  </div>
                  <h1>{view === "review" ? "Workflow & approvals" : visibleSteps?.find(s=>s.id===selectedStep)?.name || "Step document"}</h1>
                  <p className="fs-lead">{view === "review" ? "Review saved documents and media. Set where the workflow needs your approval." : "Prepare the saved document for this project step."}</p>
                </div>
              </div>
              <div className={`fs-workflow ${view === "workflow" ? "fs-document-workflow" : ""}`}>
                {view === "review" && <div className="fs-stage-nav">
                  {visibleSteps?.map((s, i) => (
                    <div
                      key={s.id}
                      className={`fs-stage-row ${selectedStep === s.id ? "selected" : ""}`}
                    >
                      <button aria-current={selectedStep === s.id ? "step" : undefined} onClick={() => openStep(s.id, view === "review")}>
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
                </div>}
                <div className="fs-stage-content">
                  <div className="fs-eyebrow">
                    {caps?.steps
                      .find((s) => s.id === selectedStep)
                      ?.name.toUpperCase()}
                  </div>
                  <h2>
                    {pretty(project.steps[selectedStep]?.status || "draft")}
                  </h2>
                  {(["brief", "script", "editor_handoff"].includes(selectedStep) || (imageOnly && selectedStep === "final_review")) && (
                    <StepDocument key={project.id+":"+selectedStep} project={project} step={selectedStep} busy={busy}
                      save={fn=>act(fn,"Step prepared")} onState={setDocumentDirty} />
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
                  {selectedStep === "final_review" && imageOnly && <div className="fs-image-final-review"><p className="fs-body">Review the selected images and their recorded quality checks before completing this project.</p><div className="fs-media-strip">{project.assets.filter(a=>!a.stale && a.kind==="image" && project.shots.some(s=>s.image_asset===a.id)).map(a=><img key={a.id} src={a.url} alt="Selected image for final review"/>)}</div><button className="fs-button" onClick={()=>navigate({view:"takes"})}>Inspect selected images</button></div>}
                  {selectedStep === "final_review" && !imageOnly && (
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
                                    expected_revision: project.revision,
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
                                    expected_revision: project.revision,
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
                </div>
              </div>
            </section>
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
          {project && ["generator", "import"].includes(view) && <section className="fs-generation-workspace">
            {view === "import" && <><div className="fs-eyebrow">RETURN OUTPUT</div><h1>Import generated media</h1><p className="fs-lead">Return a claimed handoff, or attach an existing image or video to its shot.</p><MediaUpload project={project} busy={busy} save={fn=>act(fn,"Media imported")}/></>}
                  {next?.action === "generate" &&
                     (
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
          </section>}
          {project && view === "sequences" && !imageOnly && <SequenceWorkspace key={project.id} project={project} busy={busy} save={fn=>act(fn,"Sequence applied")}/>}
          {project && view === "delivery" && <ImageDelivery project={project}/>}

          {project && view === "shots" && (
            <CreativeWorkspace
              key={project.id}
              project={project}
              catalog={catalog}
              busy={busy}
              inbox={caps?.inbox || ""}
              onOpenLibrary={()=>setView("knowledge")}
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
          {view === "knowledge" && <CinematographyLibrary catalog={catalog} project={project} busy={busy} save={(fn)=>act(fn,"Creative direction applied")} />}
          {project && view === "takes" && (
            <TakesWorkspace
              key={project.id}
              project={project}
              busy={busy}
              save={(fn) => act(fn, "Production evidence saved")}
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
              {templatesForOutput(caps?.templates || [],outputType).map((t) => (
                <option value={t.id} key={t.id}>
                  {t.saved ? "Saved · " : ""}
                  {t.name}
                </option>
              ))}
            </select>
            <label className="fs-label">Output type<select value={outputType} onChange={e=>{const kind=e.target.value as "image"|"video";setOutputType(kind);setTemplate(templateForOutput(caps?.templates||[],kind,template));}}><option value="image">Image</option><option value="video">Video</option></select></label>
            {["image",...(outputType==="video"?["video"]:[])].map(kind=><div key={kind}><label className="fs-label">{kind==="image"?"Image":"Video"} generator profile<select value={generators[`${kind}_generator` as keyof typeof generators]} onChange={e=>setGenerators({...generators,[`${kind}_generator`]:e.target.value})}><option value="">Choose a profile</option>{(kind==="image"?caps?.image_profiles:caps?.video_profiles)?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label className="fs-label">{kind==="image"?"Image":"Video"} model name<input value={generators[`${kind}_model` as keyof typeof generators]} onChange={e=>setGenerators({...generators,[`${kind}_model`]:e.target.value})}/></label></div>)}
            <details><summary>Creative brief · answer now or after creating</summary><BriefFields answers={brief} onChange={setBrief}/></details>
            <p className="fs-hint">
              {caps?.templates
                .find((t) => t.id === template)
                ?.structure.join(" → ")}
            </p>
            <button
              className="fs-primary"
              disabled={busy || !template || !name.trim() || !generators.image_generator || !generators.image_model.trim() || (outputType==="video" && (!generators.video_generator || !generators.video_model.trim()))}
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
  const config = mcpConfig(caps?.mcp_launch,client);
  return (
    <section>
      <div className="fs-eyebrow">CONNECTIONS</div>
      <h1>Your agent runs the workflow.</h1>
      <p className="fs-lead">
        Connect once. Your agent reads the next step, takes a generation
        handoff, and returns the real output.
      </p>
      <details className="fs-legacy-tools"><summary>Advanced companion tools</summary><p className="fs-hint"><a href="/">Open legacy companion dashboard</a></p></details>
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
            {caps?.mcp_launch?.desktop ? "Keep Orchestra open while your agent uses MCP." : "Setup instructions: docs/MCP.md in the project folder."}
            Client configurations are provided, not silently installed.
          </p>
          <h3>Try this in your agent</h3>
          <p className="fs-hint">
            Agents must acknowledge the current workflow contract before editing.
            Orchestra checks revisions, permitted workflow steps and your review
            policy on the server. Reconnect your MCP client after upgrading to
            load the new tools.
          </p>
          <blockquote>
            “Use Orchestra to create a short drama. Read and acknowledge its current workflow contract, then prepare the brief and
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
