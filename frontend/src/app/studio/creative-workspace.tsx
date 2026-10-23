"use client";
import { useState } from "react";
import {
  Plus,
  ArrowUp,
  ArrowDown,
  Clapperboard,
  ArrowRight,
} from "lucide-react";
import { studioApi as api } from "./client";
import { DraftNotice, Field, PairEditor, useDraft } from "./creative-forms";
import { TechniqueVisual } from "./visual-help";
import { ControlModeSwitch, ModeDetail, useControlMode } from "./control-mode";
import {
  emptyDirection,
  mergeRecord,
  type Project,
  type Shot,
  type Direction,
  type Catalog,
  type Technique,
  type Save,
  type Preflight,
} from "./creative-types";

const tabs = [
  "Story",
  "Camera",
  "Lighting",
  "Art",
  "References",
  "Continuity",
  "Sound",
  "Quality",
];
const cameraFields = [
  ["body_look", "Camera look", "camera"],
  ["lens", "Lens feel", "lens"],
  ["aperture", "Aperture / depth cue", "lens"],
  ["framing", "Shot size", "framing"],
  ["angle", "Camera angle", "framing"],
  ["position", "Camera position", "framing"],
  ["foreground", "Foreground", "framing"],
  ["midground", "Midground", "framing"],
  ["background", "Background", "framing"],
  ["lead_room", "Lead room", "framing"],
  ["screen_direction", "Screen direction", "continuity"],
  ["move", "Main camera movement", "movement"],
  ["speed", "Movement speed", "movement"],
  ["start_framing", "Starting composition", "framing"],
  ["end_framing", "Ending composition", "framing"],
  ["move_timing", "Movement timing", "movement"],
];
const lightingFields = [
  ["technique", "Lighting technique"],
  ["world_source", "Physical light source"],
  ["direction", "Camera-relative light direction"],
  ["softness", "Source softness"],
  ["contrast", "Contrast / shadow depth"],
  ["temperature", "Colour temperature / tint"],
  ["practicals", "Visible practicals"],
  ["material_response", "Material response"],
];

export function Checks({
  checks,
  shots = [],
}: {
  checks: Preflight;
  shots?: Shot[];
}) {
  return (
    <div className="cv-checks">
      <div className="cv-check-summary">
        <strong>
          {checks.errors} blocking · {checks.warnings} advisory
        </strong>
        <span>{checks.retained_seconds}s retained</span>
      </div>
      {checks.issues.map((i, n) => (
        <div
          className={`cv-issue ${i.severity}`}
          key={`${i.rule}-${i.shot_id}-${n}`}
        >
          <span>{i.severity === "error" ? "!" : "·"}</span>
          <div>
            <strong>
              {shots.find((s) => s.id === i.shot_id)?.title || "Project"} ·{" "}
              {i.rule.replaceAll("_", " ")}
            </strong>
            <p>{i.message}</p>
          </div>
        </div>
      ))}
      <small>{checks.scope}</small>
    </div>
  );
}

export function CreativeWorkspace({
  project,
  busy,
  save,
  inbox,
  catalog,
  onOpenLibrary,
}: {
  project: Project;
  busy: boolean;
  save: Save;
  inbox: string;
  catalog: Catalog | null;
  onOpenLibrary?: () => void;
}) {
  const imageOnly = project.output_type === "image";
  const [mode, setMode] = useControlMode("directing");
  const plan = useDraft(project.shots, project.revision, `shots:${project.id}`),
    defaults = useDraft(
      project.settings,
      project.revision,
      `settings:${project.id}`,
    );
  const [selected, setSelected] = useState(project.shots[0]?.id || ""),
    [tab, setTab] = useState("Story");
  const [storedPreview, setPreview] = useState<{
    source_revision: number;
    image: { prompt: string };
    video: { prompt: string };
    preflight: Preflight;
  } | null>(null);
  const [previewError, setPreviewError] = useState(""),
    [path, setPath] = useState(""),
    [referenceName, setReferenceName] = useState("");
  const shots = plan.draft;
  const index = Math.max(
    0,
    shots.findIndex((s) => (s.id || s._draft_key) === selected),
  );
  const shot = shots[index],
    d = shot?.direction || emptyDirection();
  const preview =
    storedPreview?.source_revision === project.revision ? storedPreview : null;
  function edit(patch: Partial<Shot>) {
    plan.edit((list) =>
      list.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    );
    setPreview(null);
  }
  function dir(patch: Partial<Direction>) {
    edit({ direction: mergeRecord(d, patch) });
  }
  function technique(entry: Technique) {
    const next = mergeRecord(d, entry.apply);
    next.technique_ids = [...new Set([...d.technique_ids, entry.id])];
    edit({ direction: next });
  }
  const common = { entries: catalog?.entries || [], onApply: technique };
  const inherited = (group: "camera" | "lighting" | "art", key: string) =>
    project.production.defaults[group]?.[key] ||
    ({
      lens: "lens",
      framing: "framing",
      move: "camera_move",
      technique: "lighting",
      style: "style",
      palette: "palette",
    }[key] &&
      String(
        project.settings[
          (
            {
              lens: "lens",
              framing: "framing",
              move: "camera_move",
              technique: "lighting",
              style: "style",
              palette: "palette",
            } as Record<string, string>
          )[key]
        ],
      )) ||
    "Custom direction";
  if (!shot) return null;
  const media = project.assets.find(
    (a) => a.id === (shot.video_asset || shot.image_asset),
  );
  const category =
    tab === "Camera"
      ? "movement"
      : tab === "Lighting"
        ? "lighting"
        : tab === "Art"
          ? "style"
          : tab === "Sound"
            ? "sound"
            : tab === "Continuity"
              ? "continuity"
              : "story";
  return (
    <section className="cv-workspace">
      <div className="fs-heading">
        <div>
          <div className="fs-eyebrow">DIRECTING WORKSPACE</div>
          <h1>Shots & direction</h1>
          <p className="fs-lead">
            Direct each shot. Blank controls inherit project values; custom
            direction is always available.
          </p>
        </div>
        <span className="fs-badge">
          {plan.dirty
            ? "Unapplied direction"
            : `${shots.length} shots · ${shots.reduce((n, s) => n + s.edit_duration_seconds, 0)}s edit`}
        </span>
      </div>
      <ControlModeSwitch mode={mode} onChange={setMode} label="Directing" />
      {onOpenLibrary && <button type="button" className="fs-button" onClick={onOpenLibrary}>Explore camera, angles & lighting examples <ArrowRight size={14}/></button>}
      <DraftNotice {...plan} />
      <div className="cv-director">
        <div className="cv-shot-rail">
          <div className="cv-rail-heading">
            <span>SHOT ORDER</span>
            <button
              className="fs-link"
              disabled={busy}
              onClick={() => {
                const s = {
                  id: "",
                  _draft_key: crypto.randomUUID(),
                  title: `Shot ${shots.length + 1}`,
                  image_prompt: "",
                  motion_prompt: "",
                  narration: "",
                  duration_seconds: 4,
                  edit_duration_seconds: 4,
                  image_asset: null,
                  video_asset: null,
                  direction: emptyDirection(),
                };
                plan.edit((list) => [...list, s]);
                setSelected(s._draft_key);
              }}
            >
              <Plus size={14} /> Add
            </button>
          </div>
          {shots.map((s, i) => (
            <button
              key={s.id || s._draft_key || `new-${i}`}
              className={`cv-shot-choice ${i === index ? "active" : ""}`}
              onClick={() => {
                setSelected(s.id || s._draft_key || "");
                setPreview(null);
              }}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              <div>
                <strong>{s.title}</strong>
                <small>
                  {s.direction.scene_id || "Scene unassigned"} ·{" "}
                  {s.edit_duration_seconds}s
                </small>
              </div>
              <i
                className={
                  s.video_asset ? "has-video" : s.image_asset ? "has-image" : ""
                }
              />
            </button>
          ))}
          <p className="fs-hint">
            Generation and edit order have distinct IDs. Reorder with the
            selected shot controls.
          </p>
        </div>
        <div className="cv-shot-inspector">
          <div className="cv-shot-top">
            <div className="cv-shot-preview">
              {media ? (
                media.kind === "image" ? (
                  <img src={media.url} alt={shot.title} />
                ) : (
                  <video src={media.url} controls />
                )
              ) : (
                <>
                  <Clapperboard size={23} />
                  <span>No media returned</span>
                </>
              )}
            </div>
            <div className="cv-shot-meta">
              <Field
                label="Shot title"
                value={shot.title}
                onChange={(title) => edit({ title })}
              />
              {!imageOnly && <div className="cv-two">
                <Field
                  label="Edit source in-point (seconds)"
                  type="number"
                  value={shot.edit_in_seconds || 0}
                  onChange={(v) => edit({ edit_in_seconds: Number(v) })}
                />
                <Field
                  label="Generation duration (seconds)"
                  type="number"
                  value={shot.duration_seconds}
                  onChange={(v) => edit({ duration_seconds: Number(v) })}
                  help="story"
                  {...common}
                />
                <Field
                  label="Retained edit (seconds)"
                  type="number"
                  value={shot.edit_duration_seconds}
                  onChange={(v) => edit({ edit_duration_seconds: Number(v) })}
                  help="story"
                  {...common}
                />
              </div>}
            </div>
          </div>
          <div
            role="tablist"
            aria-label="Shot direction sections"
            className="cv-tabs"
          >
            {tabs.filter(t=>!imageOnly || !["Sound","Continuity"].includes(t)).map((t) => (
              <button
                role="tab"
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <div
            className="cv-inspector-body"
            role="tabpanel"
            aria-label={`${tab} direction`}
          >
            {tab === "Story" && (
              <>
                <div className="cv-form-grid">
                  <Field
                    label="Scene ID"
                    value={d.scene_id}
                    onChange={(scene_id) => dir({ scene_id })}
                  />
                  <Field
                    label="Story purpose"
                    value={d.story_purpose}
                    onChange={(story_purpose) => dir({ story_purpose })}
                    help="story"
                    {...common}
                  />
                  <Field
                    label={imageOnly ? "Visual concept" : "Script beat"}
                    value={d.script_beat}
                    onChange={(script_beat) => dir({ script_beat })}
                  />
                    <Field label="Why these creative choices?" multiline value={d.decision_reason || ""} onChange={(decision_reason)=>dir({decision_reason})} placeholder="Explain how framing, camera movement and light serve this beat."/>
                    <Field label="Recipe shot role" value={d.recipe_role || ""} onChange={(recipe_role)=>dir({recipe_role})} placeholder="Use the role ID in the recipe contract, or leave custom."/>
                  <Field
                    label="Environment"
                    value={d.environment}
                    onChange={(environment) => dir({ environment })}
                  />
                  <Field
                    label="Mood"
                    value={d.mood}
                    onChange={(mood) => dir({ mood })}
                    help="style"
                    {...common}
                  />
                </div>
                <Field
                  label="Image subject / base prompt"
                  multiline
                  value={shot.image_prompt}
                  onChange={(image_prompt) => edit({ image_prompt })}
                />
                {!imageOnly && <>
                <Field
                  label="Motion / base prompt"
                  multiline
                  value={shot.motion_prompt}
                  onChange={(motion_prompt) => edit({ motion_prompt })}
                />
                <Field
                  label="Narration"
                  multiline
                  value={shot.narration}
                  onChange={(narration) => edit({ narration })}
                />
                </>}
              </>
            )}
            {tab === "Camera" && (
              <div className="cv-form-grid">
                {cameraFields.filter(([key])=>!imageOnly || !["move","speed","start_framing","end_framing","move_timing"].includes(key)).map(([key, label, help]) => (
                  <ModeDetail
                    key={key}
                    mode={mode}
                    advanced={!["body_look", "lens", "framing", "angle", "move", "screen_direction"].includes(key)}
                  >
                    <Field
                      label={label}
                      value={d.camera[key] || ""}
                      options={[
                        ...new Set(
                          (catalog?.entries || []).flatMap((e) =>
                            e.apply.camera?.[key] ? [e.apply.camera[key]] : [],
                          ),
                        ),
                      ]}
                      placeholder={`Inherit: ${inherited("camera", key)}`}
                      onChange={(v) => dir({ camera: { [key]: v } })}
                      help={help}
                      {...common}
                    />
                  </ModeDetail>
                ))}
              </div>
            )}
            {tab === "Lighting" && (
              <div className="cv-form-grid">
                {lightingFields.map(([key, label]) => (
                  <ModeDetail
                    key={key}
                    mode={mode}
                    advanced={!["technique", "world_source", "softness", "temperature"].includes(key)}
                  >
                    <Field
                      label={label}
                      value={d.lighting[key] || ""}
                      options={[
                        ...new Set(
                          (catalog?.entries || []).flatMap((e) =>
                            e.apply.lighting?.[key]
                              ? [e.apply.lighting[key]]
                              : [],
                          ),
                        ),
                      ]}
                      placeholder={`Inherit: ${inherited("lighting", key)}`}
                      onChange={(v) => dir({ lighting: { [key]: v } })}
                      help="lighting"
                      {...common}
                    />
                  </ModeDetail>
                ))}
              </div>
            )}
            {tab === "Art" && (
              <div className="cv-form-grid">
                {[
                  ["style", "Visual treatment"],
                  ["palette", "Colour palette"],
                  ["materials", "Material rules"],
                  ["texture", "Texture"],
                ].map(([key, label]) => (
                  <ModeDetail
                    key={key}
                    mode={mode}
                    advanced={!["style", "palette"].includes(key)}
                  >
                    <Field
                      label={label}
                      value={d.art[key] || ""}
                      options={[
                        ...new Set(
                          (catalog?.entries || []).flatMap((e) =>
                            e.apply.art?.[key] ? [e.apply.art[key]] : [],
                          ),
                        ),
                      ]}
                      placeholder={`Inherit: ${inherited("art", key)}`}
                      onChange={(v) => dir({ art: { [key]: v } })}
                      help={key === "palette" ? "palette" : "style"}
                      {...common}
                    />
                  </ModeDetail>
                ))}
              </div>
            )}
            {tab === "References" && (
              <>
                <p className="fs-body">
                  Bind the real upload slot to an imported image and immutable
                  asset version. Without bindings, legacy handoffs include all
                  project references.
                </p>
                <label className="fs-label">
                  Generation mode
                  <select
                    value={d.generation_mode}
                    onChange={(e) => dir({ generation_mode: e.target.value })}
                  >
                    {[
                      ["inherit", "Use profile default"],
                      ["text_to_video", "Text to video"],
                      ["image_to_video", "Image to video"],
                      ["start_end", "Start + end frames"],
                      ["motion_control", "Motion reference planning"],
                    ].filter(([v])=>!imageOnly || v==="inherit").map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
                {d.references.map((r, i) => (
                  <div className="cv-reference-row" key={i}>
                    <Field
                      label={`Upload slot ${i + 1}`}
                      value={r.slot}
                      onChange={(slot) =>
                        dir({
                          references: d.references.map((v, n) =>
                            n === i ? { ...v, slot } : v,
                          ),
                        })
                      }
                    />
                    <label className="fs-label">
                      Reference image
                      <select
                        value={r.asset_id}
                        onChange={(e) =>
                          dir({
                            references: d.references.map((v, n) =>
                              n === i ? { ...v, asset_id: e.target.value } : v,
                            ),
                          })
                        }
                      >
                        <option value="">Choose imported image</option>
                        {project.assets
                          .filter(
                            (a) =>
                              a.kind ===
                              (r.role === "motion" ? "video" : "image"),
                          )
                          .map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name || a.id.slice(0, 8)}
                              {a.stale ? " · earlier take" : ""}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="fs-label">
                      Role
                      <select
                        value={r.role}
                        onChange={(e) =>
                          dir({
                            references: d.references.map((v, n) =>
                              n === i ? { ...v, role: e.target.value } : v,
                            ),
                          })
                        }
                      >
                        {[
                          "character",
                          "location",
                          "prop",
                          "style",
                          "start_frame",
                          "end_frame",
                          "motion",
                          "mask",
                        ].map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                    <Field
                      label={`Reference version ${i + 1}`}
                      type="number"
                      value={r.version}
                      onChange={(v) =>
                        dir({
                          references: d.references.map((ref, n) =>
                            n === i ? { ...ref, version: Number(v) } : ref,
                          ),
                        })
                      }
                    />
                    <label className="fs-label">
                      Bible entity
                      <select
                        value={r.entity_id}
                        onChange={(e) =>
                          dir({
                            references: d.references.map((v, n) =>
                              n === i ? { ...v, entity_id: e.target.value } : v,
                            ),
                          })
                        }
                      >
                        <option value="">Unassigned</option>
                        {project.production.bible.map((e) => (
                          <option key={e.id} value={e.id}>
                            {e.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <Field
                      label={`Reference notes ${i + 1}`}
                      value={r.notes}
                      onChange={(notes) =>
                        dir({
                          references: d.references.map((v, n) =>
                            n === i ? { ...v, notes } : v,
                          ),
                        })
                      }
                    />
                    <button
                      className="fs-link"
                      onClick={() =>
                        dir({
                          references: d.references.filter((_, n) => n !== i),
                        })
                      }
                    >
                      Remove binding
                    </button>
                  </div>
                ))}
                <button
                  className="fs-button"
                  onClick={() =>
                    dir({
                      references: [
                        ...d.references,
                        {
                          slot: `reference_${d.references.length + 1}`,
                          asset_id: "",
                          version: 1,
                          role: "character",
                          entity_id: "",
                          notes: "",
                        },
                      ],
                    })
                  }
                >
                  Add reference binding
                </button>
                <div className="cv-reference-import">
                  <h3>Import a real reference</h3>
                  <code className="fs-path">{inbox}</code>
                  <Field
                    label="Reference name"
                    value={referenceName}
                    onChange={setReferenceName}
                  />
                  <Field
                    label="Reference media path"
                    value={path}
                    onChange={setPath}
                  />
                  <button
                    className="fs-button"
                    disabled={busy || !path || plan.dirty}
                    onClick={() =>
                      save(() =>
                        api("import_reference", {
                          project_id: project.id,
                          path,
                          kind: path.toLowerCase().endsWith(".mp4")
                            ? "video"
                            : "image",
                          name: referenceName || "Creative reference",
                          expected_revision: project.revision,
                        }),
                      )
                    }
                  >
                    Import image / motion video
                  </button>
                  <p className="fs-hint">
                    Apply shot edits before importing. The source file must be
                    in the studio inbox. PNG, JPEG, WebP and MP4 motion sources
                    are supported.
                  </p>
                </div>
              </>
            )}
            {tab === "Continuity" && (
              <>
                <div className="cv-form-grid">
                  {[
                    ["opening", "Opening state / frame"],
                    ["primary_action", "Primary action"],
                    ["ending", "Ending state / frame"],
                    ["transition", "Transition explanation"],
                  ].map(([key, label]) => (
                    <Field
                      key={key}
                      label={label}
                      multiline
                      value={String(
                        d.action[key as keyof typeof d.action] || "",
                      )}
                      onChange={(v) =>
                        dir({ action: { ...d.action, [key]: v } })
                      }
                      help="continuity"
                      {...common}
                    />
                  ))}
                  <Field
                    label="Visible entity IDs (comma separated)"
                    value={d.action.visible_entities.join(", ")}
                    onChange={(v) =>
                      dir({
                        action: {
                          ...d.action,
                          visible_entities: v
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                        },
                      })
                    }
                  />
                  <Field
                    label="Visible character count"
                    type="number"
                    value={d.action.headcount ?? ""}
                    onChange={(v) =>
                      dir({
                        action: {
                          ...d.action,
                          headcount: v === "" ? null : Number(v),
                        },
                      })
                    }
                  />
                </div>
                <label className="fs-label">
                  Continues from
                  <select
                    value={d.action.continuity_from}
                    onChange={(e) =>
                      dir({
                        action: {
                          ...d.action,
                          continuity_from: e.target.value,
                        },
                      })
                    }
                  >
                    <option value="">No explicit continuation</option>
                    {shots.slice(0, index).map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title}
                      </option>
                    ))}
                  </select>
                </label>
                <PairEditor
                  label="Before state"
                  value={d.action.state_before}
                  onChange={(state_before) =>
                    dir({ action: { ...d.action, state_before } })
                  }
                />
                <PairEditor
                  label="After state"
                  value={d.action.state_after}
                  onChange={(state_after) =>
                    dir({ action: { ...d.action, state_after } })
                  }
                />
                <h3>Timed action</h3>
                {d.action.beats.map((b, i) => (
                  <div className="cv-action-beat" key={i}>
                    <Field
                      label={`Action ${i + 1} start`}
                      type="number"
                      value={b.start}
                      onChange={(v) =>
                        dir({
                          action: {
                            ...d.action,
                            beats: d.action.beats.map((x, n) =>
                              n === i ? { ...x, start: Number(v) } : x,
                            ),
                          },
                        })
                      }
                    />
                    <Field
                      label={`Action ${i + 1} end`}
                      type="number"
                      value={b.end}
                      onChange={(v) =>
                        dir({
                          action: {
                            ...d.action,
                            beats: d.action.beats.map((x, n) =>
                              n === i ? { ...x, end: Number(v) } : x,
                            ),
                          },
                        })
                      }
                    />
                    <Field
                      label={`Action ${i + 1}`}
                      value={b.description}
                      onChange={(description) =>
                        dir({
                          action: {
                            ...d.action,
                            beats: d.action.beats.map((x, n) =>
                              n === i ? { ...x, description } : x,
                            ),
                          },
                        })
                      }
                    />
                    <button
                      className="fs-link"
                      onClick={() =>
                        dir({
                          action: {
                            ...d.action,
                            beats: d.action.beats.filter((_, n) => n !== i),
                          },
                        })
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  className="fs-button"
                  onClick={() =>
                    dir({
                      action: {
                        ...d.action,
                        beats: [
                          ...d.action.beats,
                          {
                            start: 0,
                            end: shot.duration_seconds,
                            description: "",
                          },
                        ],
                      },
                    })
                  }
                >
                  Add timed action
                </button>
              </>
            )}
            {tab === "Sound" && (
              <>
                <div className="cv-form-grid">
                  {[
                    ["speaker_id", "Active speaker ID"],
                    ["dialogue", "Dialogue"],
                    ["voice", "Voice direction"],
                    ["ambience", "Ambience"],
                    ["foley", "Foley cues"],
                    ["music", "Music intent"],
                    ["captions", "Captions / end-card notes"],
                  ].map(([key, label]) => (
                    <Field
                      key={key}
                      label={label}
                      value={String(d.sound[key as keyof typeof d.sound] || "")}
                      onChange={(v) => dir({ sound: { ...d.sound, [key]: v } })}
                      help="sound"
                      {...common}
                    />
                  ))}
                  <Field
                    label="Measured speech (seconds)"
                    type="number"
                    value={d.sound.measured_seconds ?? ""}
                    onChange={(v) =>
                      dir({
                        sound: {
                          ...d.sound,
                          measured_seconds: v === "" ? null : Number(v),
                        },
                      })
                    }
                  />
                  <Field
                    label="Pauses (seconds)"
                    type="number"
                    value={d.sound.pauses_seconds ?? ""}
                    onChange={(v) =>
                      dir({
                        sound: {
                          ...d.sound,
                          pauses_seconds: v === "" ? null : Number(v),
                        },
                      })
                    }
                  />
                </div>
                <label className="fs-policy">
                  <input
                    type="checkbox"
                    checked={!!d.sound.cutaway}
                    onChange={(e) =>
                      dir({ sound: { ...d.sound, cutaway: e.target.checked } })
                    }
                  />
                  Listener cutaway · retain speaker audio, listener stays silent
                </label>
              </>
            )}
            {tab === "Quality" && (
              <>
                <Field
                  label="Acceptance criteria (one per line)"
                  multiline
                  value={d.quality.criteria.join("\n")}
                  onChange={(v) =>
                    dir({ quality: { ...d.quality, criteria: v.split("\n") } })
                  }
                  help="continuity"
                  {...common}
                />
                <Field
                  label="Known defect"
                  multiline
                  value={d.quality.known_defect}
                  onChange={(known_defect) =>
                    dir({ quality: { ...d.quality, known_defect } })
                  }
                />
                <Field
                  label="Revision reason"
                  multiline
                  value={d.quality.revision_reason}
                  onChange={(revision_reason) =>
                    dir({ quality: { ...d.quality, revision_reason } })
                  }
                />
                <Checks checks={project.preflight} shots={shots} />
              </>
            )}
            <details className="cv-techniques">
              <summary>Suggested {category} techniques</summary>
              <div>
                {catalog?.entries
                  .filter((e) => e.category === category)
                  .map((e) => (
                    <button
                      type="button"
                      key={e.id}
                      onClick={() => technique(e)}
                    >
                      <span>{e.name}</span>
                      <small>{e.use_when}</small>
                      <ArrowRight size={13} />
                    </button>
                  ))}
              </div>
            </details>
          </div>
          <div className="cv-shot-toolbar">
            <div>
              <button
                className="fs-link"
                disabled={index === 0}
                onClick={() =>
                  plan.edit((list) => {
                    const copy = [...list];
                    [copy[index - 1], copy[index]] = [
                      copy[index],
                      copy[index - 1],
                    ];
                    return copy;
                  })
                }
              >
                <ArrowUp size={13} /> Move up
              </button>
              <button
                className="fs-link"
                disabled={index === shots.length - 1}
                onClick={() =>
                  plan.edit((list) => {
                    const copy = [...list];
                    [copy[index + 1], copy[index]] = [
                      copy[index],
                      copy[index + 1],
                    ];
                    return copy;
                  })
                }
              >
                <ArrowDown size={13} /> Move down
              </button>
              <button
                className="fs-link"
                disabled={shots.length === 1}
                onClick={() => {
                  plan.edit((list) => list.filter((_, i) => i !== index));
                  setSelected(shots[0].id);
                }}
              >
                Remove shot
              </button>
            </div>
            <button
              className="fs-primary"
              disabled={busy || !plan.dirty || plan.conflict}
              onClick={() =>
                save(async () => {
                  const updated = await api<Project>("update_shots", {
                    project_id: project.id,
                    shots,
                    expected_revision: plan.revision,
                  });
                  setSelected(updated.shots[index]?.id || "");
                  plan.saved();
                })
              }
            >
              Apply shot direction
            </button>
          </div>
          <div className="cv-preview">
            <button
              className="fs-button"
              disabled={busy || plan.dirty || !shot.id}
              onClick={async () => {
                setPreviewError("");
                try {
                  setPreview(
                    await api("preview_shot", {
                      project_id: project.id,
                      shot_id: shot.id,
                    }),
                  );
                } catch (e) {
                  setPreviewError((e as Error).message);
                }
              }}
            >
              Preview compiled prompts
            </button>
            <small>
              Apply the draft first. Preview and MCP use the same compiler.
            </small>
            {previewError && <p role="alert">{previewError}</p>}
            {preview && (
              <>
                <Field
                  label="Compiled image prompt"
                  readOnly
                  multiline
                  value={preview.image.prompt}
                  onChange={() => {}}
                />
                {!imageOnly && <Field
                  label="Compiled video prompt"
                  readOnly
                  multiline
                  value={preview.video.prompt}
                  onChange={() => {}}
                />}
                <Checks checks={preview.preflight} shots={shots} />
              </>
            )}
          </div>
        </div>
      </div>
      <details className="cv-project-defaults">
        <summary>Project-wide defaults</summary>
        <DraftNotice {...defaults} />
        <div className="cv-form-grid">
          {[
            ["audience", "Audience"],
            ["platform", "Platform"],
            ["lens", "Lens"],
            ["framing", "Framing"],
            ["camera_move", "Camera movement"],
            ["lighting", "Lighting"],
            ["palette", "Palette"],
            ["style", "Visual style"],
            ["continuity", "Continuity anchors"],
            ["sound", "Sound direction"],
            ["negative_prompt", "Avoid"],
          ].filter(([key])=>!imageOnly || !["camera_move","sound"].includes(key)).map(([key, label]) => (
            <Field
              key={key}
              label={label}
              value={defaults.draft[key]}
              onChange={(v) => defaults.edit((s) => ({ ...s, [key]: v }))}
            />
          ))}
          {!imageOnly && <Field
            label="Target duration (seconds)"
            type="number"
            value={defaults.draft.duration_seconds}
            onChange={(v) =>
              defaults.edit((s) => ({ ...s, duration_seconds: Number(v) }))
            }
          />}
          <label className="fs-label">
            Aspect ratio
            <select
              value={defaults.draft.aspect_ratio}
              onChange={(e) =>
                defaults.edit((s) => ({ ...s, aspect_ratio: e.target.value }))
              }
            >
              {(imageOnly ? ["16:9", "9:16", "1:1", "4:5", "2:3"] : ["16:9", "9:16", "1:1"]).map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        </div>
        <button
          className="fs-button"
          disabled={busy || !defaults.dirty || defaults.conflict}
          onClick={() =>
            save(async () => {
              await api("update_settings", {
                project_id: project.id,
                settings: defaults.draft,
                expected_revision: defaults.revision,
              });
              defaults.saved();
            })
          }
        >
          Apply creative settings
        </button>
      </details>
    </section>
  );
}

export function TechniqueLibrary({ catalog }: { catalog: Catalog | null }) {
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("");
  return (
    <section>
      <div className="fs-eyebrow">REFERENCE LIBRARY</div>
      <h1>Techniques & visual guides</h1>
      <p className="fs-lead">
        Explore a look, understand the tradeoff, then apply it from the shot
        inspector.
      </p>
      <div className="cv-library-search">
        <Field label="Search techniques" value={query} onChange={setQuery} />
        <label className="fs-label">
          Category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {catalog?.categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <p className="cv-coverage">
        {catalog?.coverage.status} {catalog?.coverage.entry_count} available
        entries. {catalog?.coverage.limitations}
      </p>
      <div className="cv-library">
        {catalog?.entries
          .filter(
            (e) =>
              (!category || e.category === category) &&
              `${e.name} ${e.explanation} ${e.use_when}`
                .toLowerCase()
                .includes(query.toLowerCase()),
          )
          .map((e) => (
            <article key={e.id}>
              <TechniqueVisual kind={e.category} variant={e.visual.variant} />
              <div>
                <div className="fs-eyebrow">{e.category}</div>
                <h2>{e.name}</h2>
                <p>{e.explanation}</p>
                <p>
                  <strong>Use for:</strong> {e.use_when}
                </p>
                <p>
                  <strong>Watch for:</strong> {e.risk}
                </p>
                <small>
                  {e.source} · {e.source_note}
                </small>
              </div>
            </article>
          ))}
      </div>
    </section>
  );
}
