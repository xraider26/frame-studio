"use client";
import {MediaUpload} from "./media-upload";
import { useEffect, useState } from "react";
import { studioApi as api } from "./client";
import { DraftNotice, Field, useDraft } from "./creative-forms";
import { ProjectDirection } from "./project-direction";
import { ControlModeSwitch, ModeDetail, useControlMode } from "./control-mode";
import type {
  Project,
  Production,
  Entity,
  Save,
  Catalog,
} from "./creative-types";

export function ProductionWorkspace({
  project,
  view,
  busy,
  save,
  catalog,
}: {
  project: Project;
  view: "story" | "bible" | "production";
  busy: boolean;
  save: Save;
  catalog: Catalog | null;
}) {
  const [previewImage,setPreviewImage]=useState<{url:string;name:string}|null>(null);
  const imageOnly=project.output_type==="image";
  const [capabilityMedium, setCapabilityMedium] = useState<"image" | "video">("image");
  const [mode, setMode] = useControlMode("production");
  const form = useDraft(
      project.production,
      project.revision,
      `production:${project.id}:${view}`,
    ),
    p = form.draft;
  const [metrics, setMetrics] = useState<Record<
    string,
    number | string | null
  > | null>(null);
  useEffect(() => {
    if (view === "production")
      api<Record<string, number | string | null>>("production_metrics", {
        project_id: project.id,
      })
        .then(setMetrics)
        .catch(() => setMetrics(null));
  }, [view, project.id, project.revision]);
  function change(patch: Partial<Production>) {
    form.edit((old) => ({ ...old, ...patch }));
  }
  const adopted = !!project.generation_setup;
  const capabilityKind = imageOnly ? "image" : capabilityMedium;
  const emptyCapabilities: Production["capabilities"] = {model:"",confirmed:false,source:"",observed_at:"",modes:[],durations:[],aspects:[],max_references:null,audio:null};
  const capabilities = adopted ? p.capabilities_by_kind?.[capabilityKind] || emptyCapabilities : p.capabilities;
  const observingVideo = adopted ? capabilityKind === "video" : !imageOnly;
  function updateCapability(patch: Partial<Production["capabilities"]>) {
    if (adopted) {
      const observations = p.capabilities_by_kind || {image:emptyCapabilities,video:emptyCapabilities};
      change({capabilities_by_kind:{...observations,[capabilityKind]:{...capabilities,...patch}}});
    } else change({capabilities:{...capabilities,...patch}});
  }
  function entity(index: number, patch: Partial<Entity>) {
    change({
      bible: p.bible.map((e, i) => (i === index ? { ...e, ...patch } : e)),
    });
  }
  const title = {
    story: imageOnly ? "Visual concept" : "Story & timing",
    bible: "Production bible",
    production: "Production settings",
  }[view];
  return (
    <section>
      {previewImage && <div className="fs-modal-backdrop" onClick={()=>setPreviewImage(null)}><section className="fs-modal" role="dialog" aria-modal="true" aria-label={previewImage.name} onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==="Escape")setPreviewImage(null);}}><button autoFocus className="fs-button" onClick={()=>setPreviewImage(null)}>Close preview</button><img style={{width:"100%",maxHeight:"75vh",objectFit:"contain"}} src={previewImage.url} alt={previewImage.name}/></section></div>}
      <div className="fs-heading">
        <div>
          <div className="fs-eyebrow">
            {view === "bible"
              ? "CANONICAL REFERENCES"
              : view === "story"
                ? "WRITING & PLANNING"
                : "CAPABILITIES, QUALITY & RESOURCES"}
          </div>
          <h1>{title}</h1>
          <p className="fs-lead">
            {view === "story"
              ? "Build the promise and payoff, then time the beats before generating."
              : view === "bible"
                ? "Give characters, places and objects stable identities and real reference images."
                : "Record the model controls you actually observed and set your production limits."}
          </p>
        </div>
        <span className="fs-badge">
          {form.dirty ? "Unapplied changes" : "Saved production plan"}
        </span>
      </div>
      {view === "production" && (
        <ControlModeSwitch mode={mode} onChange={setMode} label="Production" />
      )}
      <DraftNotice {...form} />
      <details className="cv-format-rules">
        <summary>
          {project.template_id.replaceAll("-", " ")} · format guidance
        </summary>
        <ul>
          {p.format_rules.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </details>
      {view === "story" && (
        <>
          <div className="cv-form-grid">
            {[
              ["premise", "Story premise"],
              ["promise", "Viewer promise"],
              ["niche", "Niche / subject"],
              ["opening", "Opening"],
              ["payoff", "Payoff"],
              ["factual_requirements", "Factual requirements"],
              ["factual_sources", "Sources / evidence"],
            ].map(([key, label]) => (
              <Field
                key={key}
                label={label}
                multiline
                value={p.brief[key]}
                onChange={(v) => change({ brief: { ...p.brief, [key]: v } })}
              />
            ))}
          </div>
          {!imageOnly && <>
          <div className="cv-section">
            <h2>Hooks & framework</h2>
            <p className="fs-body">
              Story framework and visual format are independent. Alternatives
              should make genuinely different promises.
            </p>
            <Field
              label="Hook alternatives (one per line)"
              multiline
              value={p.story.hooks.join("\n")}
              onChange={(v) =>
                change({ story: { ...p.story, hooks: v.split("\n") } })
              }
            />
            <Field
              label="Chosen hook"
              value={p.story.selected_hook}
              onChange={(selected_hook) =>
                change({ story: { ...p.story, selected_hook } })
              }
              help="story"
              entries={catalog?.entries}
            />
            <Field
              label="Story framework"
              value={p.story.framework}
              onChange={(framework) =>
                change({ story: { ...p.story, framework } })
              }
              help="story"
              entries={catalog?.entries}
            />
            <div className="cv-frameworks">
              {[
                "Hook → discovery → payoff",
                "Problem → demonstration → takeaway",
                "Character → conflict → reversal",
                "Question → explanation → example",
                "Host prompt → response → reflection",
              ].map((v) => (
                <button
                  className="fs-button"
                  key={v}
                  onClick={() =>
                    change({ story: { ...p.story, framework: v } })
                  }
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div className="cv-section">
            <div className="cv-section-heading">
              <h2>Timed story beats</h2>
              <span>
                {p.story.beats.reduce((n, b) => n + b.duration_seconds, 0)}s /{" "}
                {project.settings.duration_seconds}s target
              </span>
            </div>
            {p.story.beats.map((b, i) => (
              <article className="cv-beat" key={b.id}>
                <div className="cv-form-grid">
                  {[
                    ["title", "Beat title"],
                    ["narration", "Narration"],
                    ["dialogue", "Dialogue"],
                    ["action", "Visible action"],
                    ["captions", "Captions"],
                    [
                      "fact_or_dramatization",
                      "Fact / dramatisation / illustration",
                    ],
                  ].filter(([key])=>!imageOnly || key!=="video_cost").map(([key, label]) => (
                    <Field
                      key={key}
                      label={`${label} ${i + 1}`}
                      value={String(b[key as keyof typeof b] || "")}
                      onChange={(v) =>
                        change({
                          story: {
                            ...p.story,
                            beats: p.story.beats.map((x, n) =>
                              n === i ? { ...x, [key]: v } : x,
                            ),
                          },
                        })
                      }
                    />
                  ))}
                  <Field
                    label={`Beat ${i + 1} duration`}
                    type="number"
                    value={b.duration_seconds}
                    onChange={(v) =>
                      change({
                        story: {
                          ...p.story,
                          beats: p.story.beats.map((x, n) =>
                            n === i ? { ...x, duration_seconds: Number(v) } : x,
                          ),
                        },
                      })
                    }
                  />
                  <Field
                    label={`Beat ${i + 1} measured speech`}
                    type="number"
                    value={b.measured_seconds ?? ""}
                    onChange={(v) =>
                      change({
                        story: {
                          ...p.story,
                          beats: p.story.beats.map((x, n) =>
                            n === i
                              ? {
                                  ...x,
                                  measured_seconds: v === "" ? null : Number(v),
                                }
                              : x,
                          ),
                        },
                      })
                    }
                  />
                </div>
                <button
                  className="fs-link"
                  onClick={() =>
                    change({
                      story: {
                        ...p.story,
                        beats: p.story.beats.filter((_, n) => n !== i),
                      },
                    })
                  }
                >
                  Remove beat
                </button>
              </article>
            ))}
            <button
              className="fs-button"
              onClick={() =>
                change({
                  story: {
                    ...p.story,
                    beats: [
                      ...p.story.beats,
                      {
                        id: crypto.randomUUID(),
                        title: "New beat",
                        duration_seconds: 0,
                        narration: "",
                        dialogue: "",
                        action: "",
                        captions: "",
                        measured_seconds: null,
                        fact_or_dramatization: "",
                      },
                    ],
                  },
                })
              }
            >
              Add beat
            </button>
            <button
              className="fs-link"
              disabled={!p.story.beats.length}
              onClick={() => {
                const total = p.story.beats.reduce(
                  (n, b) => n + b.duration_seconds,
                  0,
                );
                const target = Number(project.settings.duration_seconds);
                let used = 0;
                change({
                  story: {
                    ...p.story,
                    beats: p.story.beats.map((b, i) => {
                      const duration_seconds =
                        i === p.story.beats.length - 1
                          ? Math.round((target - used) * 100) / 100
                          : Math.round(
                              (total
                                ? b.duration_seconds / total
                                : 1 / p.story.beats.length) *
                                target *
                                100,
                            ) / 100;
                      used += duration_seconds;
                      return { ...b, duration_seconds };
                    }),
                  },
                });
              }}
            >
              Fit beat durations to target (speech stays unchanged)
            </button>
          </div>
          </>}
        </>
      )}
      {view === "bible" && (
        <>
          <p className="fs-body">
            Upload images directly to each entity, or attach existing references.
            Identity versions and file IDs are separate; changing a bible record
            does not rewrite a file.
          </p>
          {p.bible.map((e, i) => (
            <article className="cv-entity" key={i}>
              <div className="cv-entity-heading">
                <span>
                  {e.kind} · {e.id || "ID required"} · v{e.version}
                </span>
                <button
                  className="fs-link"
                  onClick={() =>
                    change({ bible: p.bible.filter((_, n) => n !== i) })
                  }
                >
                  Remove entity
                </button>
              </div>
              <div className="cv-form-grid">
                <Field
                  label={`Entity ${i + 1} ID`}
                  value={e.id}
                  onChange={(id) => entity(i, { id })}
                />
                <Field
                  label={`Entity ${i + 1} name`}
                  value={e.name}
                  onChange={(name) => entity(i, { name })}
                />
                <label className="fs-label">
                  Kind
                  <select
                    value={e.kind}
                    onChange={(event) =>
                      entity(i, { kind: event.target.value })
                    }
                  >
                    {["character", "location", "prop", "style"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <Field
                  label={`Entity ${i + 1} version`}
                  type="number"
                  value={e.version}
                  onChange={(v) => entity(i, { version: Number(v) })}
                />
                {[
                  ["identity", "Identity / appearance"],
                  ["wardrobe", "Wardrobe variants"],
                  ["voice", "Voice direction"],
                  ["layout", "Location layout"],
                  ["light_sources", "Physical light sources"],
                  ["materials", "Materials / style rules"],
                ].filter(([key])=>!imageOnly || key!=="video_cost").map(([key, label]) => (
                  <Field
                    key={key}
                    label={`${label} · ${e.name || i + 1}`}
                    multiline
                    value={String(e[key as keyof Entity] || "")}
                    onChange={(v) => entity(i, { [key]: v })}
                  />
                ))}
              </div>
              <MediaUpload project={project} busy={busy} save={save} entityId={e.id} disabled={form.dirty || !project.production.bible.some(v=>v.id===e.id)}/>
              <p className="fs-hint">Select images to attach; uncheck to detach. Files remain in the project.</p>
              <div className="cv-bible-assets">
                {project.assets
                  .filter((a) => a.kind === "image")
                  .map((a) => (
                    <label key={a.id}>
                      <input
                        type="checkbox"
                        checked={e.asset_ids.includes(a.id)}
                        onChange={(event) =>
                          entity(i, {
                            asset_ids: event.target.checked
                              ? [...e.asset_ids, a.id]
                              : e.asset_ids.filter((id) => id !== a.id),
                          })
                        }
                      />
                      <button type="button" className="cv-reference-preview" aria-label={`Preview ${a.name || "reference"}`} onClick={event=>{event.preventDefault();setPreviewImage({url:a.url,name:a.name||"Reference"});}}><img src={a.url} alt={a.name || "Reference"} /></button>
                      <span>{a.name || a.id.slice(0, 8)}</span>
                    </label>
                  ))}
              </div>
            </article>
          ))}
          <button
            className="fs-button"
            onClick={() =>
              change({
                bible: [
                  ...p.bible,
                  {
                    id: `entity-${p.bible.length + 1}`,
                    kind: "character",
                    name: "New character",
                    version: 1,
                    identity: "",
                    wardrobe: "",
                    voice: "",
                    layout: "",
                    light_sources: "",
                    materials: "",
                    asset_ids: [],
                  },
                ],
              })
            }
          >
            Add character, location, prop or style
          </button>
        </>
      )}
      {view === "production" && (
        <>
          <ProjectDirection
            imageOnly={imageOnly}
            mode={mode}
            value={p.defaults}
            onChange={(defaults) => change({ defaults })}
            catalog={catalog}
          />
          <div className="cv-section">
            <h2>Observed generator capabilities</h2>
            <p className="fs-body">
              A prompt profile does not prove model support. Record the actual
              controls shown by your generator.
            </p>
            {adopted && !imageOnly && <label className="fs-label">Observation medium<select aria-label="Capability medium" value={capabilityKind} onChange={e=>setCapabilityMedium(e.target.value as "image"|"video")}><option value="image">Image generator</option><option value="video">Video generator</option></select></label>}
            {adopted && <p className="fs-hint">Observations apply only to the {capabilityKind} generator. Changing that generator clears its recorded capabilities.</p>}
            <div className="cv-form-grid">
              {[
                ["model", "Model / version"],
                ["source", "Observation source / evidence"],
                ["observed_at", "Observed date"],
              ].map(([key, label]) => (
                <Field key={key} label={label} value={String(capabilities[key as keyof typeof capabilities] || "")} onChange={v=>updateCapability({[key]:v})}/>
              ))}
              <Field label="Supported modes (comma separated)" value={capabilities.modes.join(", ")} onChange={v=>updateCapability({modes:v.split(",").map(x=>x.trim()).filter(Boolean)})}/>
              {observingVideo && <Field label="Supported clip durations (comma separated)" value={capabilities.durations.join(", ")} onChange={v=>updateCapability({durations:v.split(",").filter(x=>x.trim()).map(Number)})}/>}
              <Field label="Supported aspect ratios (comma separated)" value={capabilities.aspects.join(", ")} onChange={v=>updateCapability({aspects:v.split(",").map(x=>x.trim()).filter(Boolean)})}/>
              <Field label="Maximum references" type="number" value={capabilities.max_references ?? ""} onChange={v=>updateCapability({max_references:v===""?null:Number(v)})}/>
            </div>
            <label className="fs-policy"><input type="checkbox" checked={capabilities.confirmed} onChange={e=>updateCapability({confirmed:e.target.checked})}/>I checked these controls in the specified generator</label>
            {observingVideo && <label className="fs-label">Native audio support<select value={capabilities.audio===null?"unknown":String(capabilities.audio)} onChange={e=>updateCapability({audio:e.target.value==="unknown"?null:e.target.value==="true"})}><option value="unknown">Unknown</option><option value="true">Supported</option><option value="false">Unsupported</option></select></label>}
          </div>
          <div className="cv-section">
            <h2>Quality requirements</h2>
            <label className="fs-policy">
              <input
                type="checkbox"
                checked={p.require_recorded_checks}
                onChange={(e) =>
                  change({ require_recorded_checks: e.target.checked })
                }
              />
              Require recorded media checks before a media step completes
            </label>
            <p className="fs-hint">
              This is separate from your human-approval switches. Agent evidence
              is labeled as agent evidence; it is never your approval.
            </p>
          </div>
          <div className="cv-section">
            <h2>Resources & attempt limits</h2>
            <p className="fs-body">
              Unknown costs stay unknown. Limits govern studio handoffs; an
              external tool can spend outside this studio.
            </p>
            <div className="cv-form-grid">
              <Field
                label="Cost unit (one per project)"
                value={p.resources.unit}
                onChange={(unit) =>
                  change({ resources: { ...p.resources, unit } })
                }
              />
              {[
                ["limit", "Total budget"],
                ["pilot_limit", "Pilot budget"],
                [
                  "max_attempts_per_shot",
                  "Maximum attempts per shot and media kind",
                ],
                ["image_cost", "Planned image cost"],
                ["video_cost", "Planned video cost"],
              ].filter(([key])=>!imageOnly || key!=="video_cost").map(([key, label]) => (
                <Field
                  key={key}
                  label={label}
                  type="number"
                  value={p.resources[key as keyof typeof p.resources] ?? ""}
                  placeholder="Unset / unknown"
                  onChange={(v) =>
                    change({
                      resources: {
                        ...p.resources,
                        [key]: v === "" ? null : Number(v),
                      },
                    })
                  }
                />
              ))}
              <Field
                label="Cost evidence / observation"
                multiline
                value={p.resources.cost_evidence}
                onChange={(cost_evidence) =>
                  change({ resources: { ...p.resources, cost_evidence } })
                }
              />
            </div>
            {metrics && (
              <div className="cv-metrics">
                {Object.entries(metrics)
                  .filter(([, v]) => typeof v !== "object")
                  .map(([k, v]) => (
                    <div key={k}>
                      <span>{k.replaceAll("_", " ")}</span>
                      <strong>{v === null ? "Unknown" : String(v)}</strong>
                    </div>
                  ))}
              </div>
            )}
          </div>
          <ModeDetail mode={mode}>
            <div className="cv-section">
              <h2>Pilot learning</h2>
              <p className="fs-body">
                Record sourced results and one deliberate variable. These are
                manually supplied measurements.
              </p>
              {p.experiments.map((e, i) => (
                <article className="cv-beat" key={e.id}>
                  <div className="cv-form-grid">
                    {[
                      ["variable", "Changed variable"],
                      ["hypothesis", "Hypothesis"],
                      ["result", "Observed result"],
                      ["source_date", "Measurement source / date"],
                    ].filter(([key])=>!imageOnly || key!=="video_cost").map(([key, label]) => (
                      <Field
                        key={key}
                        label={`${label} ${i + 1}`}
                        value={String(e[key as keyof typeof e] || "")}
                        onChange={(v) =>
                          change({
                            experiments: p.experiments.map((x, n) =>
                              n === i ? { ...x, [key]: v } : x,
                            ),
                          })
                        }
                      />
                    ))}
                    {[
                      ["impressions", "Impressions"],
                      ["ctr_percent", "CTR %"],
                      ["completion_percent", "Completion %"],
                    ].filter(([key])=>!imageOnly || key!=="video_cost").map(([key, label]) => (
                      <Field
                        key={key}
                        label={`${label} ${i + 1}`}
                        type="number"
                        value={e[key as keyof typeof e] ?? ""}
                        onChange={(v) =>
                          change({
                            experiments: p.experiments.map((x, n) =>
                              n === i
                                ? { ...x, [key]: v === "" ? null : Number(v) }
                                : x,
                            ),
                          })
                        }
                      />
                    ))}
                  </div>
                  <button
                    className="fs-link"
                    onClick={() =>
                      change({
                        experiments: p.experiments.filter((_, n) => n !== i),
                      })
                    }
                  >
                    Remove experiment
                  </button>
                </article>
              ))}
              <button
                className="fs-button"
                onClick={() =>
                  change({
                    experiments: [
                      ...p.experiments,
                      {
                        id: crypto.randomUUID(),
                        variable: "",
                        hypothesis: "",
                        result: "",
                        source_date: "",
                        impressions: null,
                        ctr_percent: null,
                        completion_percent: null,
                      },
                    ],
                  })
                }
              >
                Add pilot experiment
              </button>
            </div>
          </ModeDetail>
        </>
      )}
      <div className="cv-save-bar">
        <p>
          Apply to the saved production plan. Changes reopen affected work;
          existing files remain available.
        </p>
        <button
          className="fs-primary"
          disabled={busy || !form.dirty || form.conflict}
          onClick={() =>
            save(async () => {
              await api("update_production", {
                project_id: project.id,
                production: p,
                expected_revision: form.revision,
              });
              form.saved();
            })
          }
        >
          Apply{" "}
          {view === "story"
            ? "story plan"
            : view === "bible"
              ? "production bible"
              : "production settings"}
        </button>
      </div>
    </section>
  );
}
