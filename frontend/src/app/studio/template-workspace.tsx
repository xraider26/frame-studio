"use client";
import { useMemo, useState } from "react";
import { BookmarkPlus, ArrowRight, X } from "lucide-react";
import { studioApi as api } from "./client";
import { DraftNotice, Field, useDraft } from "./creative-forms";
import type { Project, Save } from "./creative-types";

export type TemplateSection = "settings" | "workflow" | "story";
export type TemplateChoice = {
  id: string;
  name: string;
  description: string;
  structure: string[];
  aspect: string;
  saved?: boolean;
  revision?: number;
  sections?: TemplateSection[];
};
export type SavedTemplate = TemplateChoice & {
  saved: true;
  revision: number;
  sections: TemplateSection[];
};
const sections: { id: TemplateSection; name: string; detail: string }[] = [
  {
    id: "settings",
    name: "Creative settings",
    detail: "Camera, light, style, generator profiles and project defaults",
  },
  {
    id: "workflow",
    name: "Workflow & quality gates",
    detail: "Approval toggles and required quality checks",
  },
  {
    id: "story",
    name: "Story & shot plan",
    detail: "Brief, beats, bible, shot directions, prompts and timing",
  },
];
const initial = {
  name: "",
  description: "",
  sections: sections.map((s) => s.id),
  settings_shot_id: "",
};

function SectionChoices({
  value,
  available,
  onChange,
  apply = false,
}: {
  value: TemplateSection[];
  available: TemplateSection[];
  onChange: (v: TemplateSection[]) => void;
  apply?: boolean;
}) {
  return (
    <fieldset className="cv-template-sections">
      <legend>{apply ? "Sections to apply" : "Include in template"}</legend>
      {sections
        .filter((s) => available.includes(s.id))
        .map((s) => (
          <label key={s.id}>
            <input
              type="checkbox"
              checked={value.includes(s.id)}
              data-section={!apply ? s.id : undefined}
              data-apply-section={apply ? s.id : undefined}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...value, s.id]
                    : value.filter((v) => v !== s.id),
                )
              }
            />
            <span>
              <strong>{s.name}</strong>
              <small>{s.detail}</small>
            </span>
          </label>
        ))}
    </fieldset>
  );
}

function CaptureTemplate({
  project,
  busy,
  save,
}: {
  project: Project;
  busy: boolean;
  save: Save;
}) {
  const form = useDraft(
    initial,
    project.revision,
    "capture-template:" + project.id,
  );
  const [savedName, setSavedName] = useState("");
  return (
    <div className="cv-template-capture">
      <div>
        <div className="fs-eyebrow">SAVE FROM {project.name}</div>
        <h2>Keep a setup that works.</h2>
        <p className="fs-body">
          Save the current project’s applied settings. Choose the parts you want
          to reuse.
        </p>
      </div>
      <div>
        <DraftNotice {...form} />
        {form.draft.sections.includes("settings") && (
          <label className="fs-label">
            Creative defaults source
            <select
              value={form.draft.settings_shot_id}
              onChange={(e) =>
                form.edit((v) => ({ ...v, settings_shot_id: e.target.value }))
              }
            >
              <option value="">Project defaults</option>
              {(project.shots || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} · use this shot’s look
                </option>
              ))}
            </select>
            <span className="fs-hint">
              Use a successful shot’s camera, lighting and art direction as
              reusable project defaults.
            </span>
          </label>
        )}
        <div className="cv-form-grid">
          <Field
            label="Template name"
            value={form.draft.name}
            onChange={(name) => form.edit((v) => ({ ...v, name }))}
            placeholder="Amber studio portrait"
          />
          <Field
            label="What worked well?"
            value={form.draft.description}
            onChange={(description) =>
              form.edit((v) => ({ ...v, description }))
            }
            placeholder="Soft north light, measured dialogue, locked camera"
          />
        </div>
        <SectionChoices
          value={form.draft.sections}
          available={sections.map((s) => s.id)}
          onChange={(value) => form.edit((v) => ({ ...v, sections: value }))}
        />
        <button
          className="fs-primary"
          disabled={
            busy ||
            form.conflict ||
            !form.draft.name.trim() ||
            !form.draft.sections.length
          }
          onClick={() =>
            save(async () => {
              await api("save_project_template", {
                project_id: project.id,
                ...form.draft,
                expected_revision: form.revision,
              });
              setSavedName(form.draft.name);
              form.reload();
            })
          }
        >
          <BookmarkPlus size={14} />
          Save as template
        </button>
        {savedName && (
          <p className="fs-hint" role="status">
            Saved “{savedName}” to your template library.
          </p>
        )}
      </div>
    </div>
  );
}

function ApplyTemplate({
  template,
  project,
  busy,
  save,
  onClose,
}: {
  template: SavedTemplate;
  project: Project;
  busy: boolean;
  save: Save;
  onClose: () => void;
}) {
  const available = useMemo(
    () => ({ sections: template.sections }),
    [template.sections],
  );
  const form = useDraft(
    available,
    project.revision,
    "apply-template:" + template.id + ":" + project.id,
  );
  return (
    <div className="cv-template-panel" aria-label={`Apply ${template.name}`}>
      <div className="cv-template-panel-title">
        <h3>Apply to {project.name}</h3>
        <button
          className="fs-link"
          aria-label="Close template options"
          onClick={onClose}
        >
          <X size={16} />
        </button>
      </div>
      <DraftNotice {...form} />
      <SectionChoices
        value={form.draft.sections}
        available={template.sections}
        apply
        onChange={(value) => form.edit(() => ({ sections: value }))}
      />
      <p className="fs-hint">
        Selected sections replace their saved project values. A story plan
        replaces the shot list and clears prepared documents. Affected outputs
        and reviews reopen; existing media files remain available.
      </p>
      <button
        className="fs-primary"
        disabled={busy || form.conflict || !form.draft.sections.length}
        onClick={() =>
          save(async () => {
            await api("apply_project_template", {
              project_id: project.id,
              template_id: template.id,
              sections: form.draft.sections,
              expected_revision: form.revision,
              template_revision: template.revision,
            });
            form.saved();
            onClose();
          })
        }
      >
        Apply selected sections
      </button>
    </div>
  );
}

function TemplateRow({
  template,
  project,
  busy,
  save,
  onNew,
}: {
  template: SavedTemplate;
  project: Project | null;
  busy: boolean;
  save: Save;
  onNew: (id: string) => void;
}) {
  const [mode, setMode] = useState<"" | "apply" | "rename" | "delete">("");
  const metadata = useMemo(
    () => ({ name: template.name, description: template.description }),
    [template.name, template.description],
  );
  const form = useDraft(
    metadata,
    template.revision,
    "rename-template:" + template.id,
  );
  return (
    <article className="cv-template-row">
      <div className="cv-template-row-main">
        <div>
          <h3>{template.name}</h3>
          <p className="fs-body">
            {template.description || "Reusable project setup"}
          </p>
          <small>
            {sections
              .filter((s) => template.sections.includes(s.id))
              .map((s) => s.name)
              .join(" · ")}
          </small>
        </div>
        <div className="cv-template-actions">
          <button
            className="fs-button"
            disabled={busy}
            onClick={() => onNew(template.id)}
          >
            New project <ArrowRight size={13} />
          </button>
          <button
            className="fs-link"
            disabled={busy || !project}
            onClick={() => setMode(mode === "apply" ? "" : "apply")}
          >
            Apply to project
          </button>
          <button
            className="fs-link"
            disabled={busy}
            onClick={() => setMode(mode === "rename" ? "" : "rename")}
          >
            Rename
          </button>
          <button
            className="fs-link"
            disabled={busy}
            onClick={() => setMode(mode === "delete" ? "" : "delete")}
          >
            Delete
          </button>
        </div>
      </div>
      {mode === "apply" && project && (
        <ApplyTemplate
          key={template.id + project.id}
          template={template}
          project={project}
          busy={busy}
          save={save}
          onClose={() => setMode("")}
        />
      )}
      {mode === "rename" && (
        <div className="cv-template-panel">
          <DraftNotice {...form} />
          <Field
            label="Saved template name"
            value={form.draft.name}
            onChange={(name) => form.edit((v) => ({ ...v, name }))}
          />
          <Field
            label="Template notes"
            value={form.draft.description}
            onChange={(description) =>
              form.edit((v) => ({ ...v, description }))
            }
          />
          <button
            className="fs-button"
            disabled={busy || form.conflict || !form.draft.name.trim()}
            onClick={() =>
              save(async () => {
                await api("rename_project_template", {
                  template_id: template.id,
                  ...form.draft,
                  expected_revision: form.revision,
                });
                form.saved();
                setMode("");
              })
            }
          >
            Save template details
          </button>
        </div>
      )}
      {mode === "delete" && (
        <div className="cv-template-panel">
          <p className="fs-body">
            Delete “{template.name}” from the library? Projects already made
            with it are kept.
          </p>
          <div className="cv-template-actions">
            <button
              className="fs-button"
              disabled={busy}
              onClick={() =>
                save(async () => {
                  await api("delete_project_template", {
                    template_id: template.id,
                    expected_revision: template.revision,
                  });
                  setMode("");
                })
              }
            >
              Delete template
            </button>
            <button className="fs-link" onClick={() => setMode("")}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function TemplateWorkspace({
  project,
  templates,
  busy,
  save,
  onNew,
}: {
  project: Project | null;
  templates: SavedTemplate[];
  busy: boolean;
  save: Save;
  onNew: (id: string) => void;
}) {
  return (
    <section
      className="cv-saved-templates"
      aria-label="Saved workflow templates"
    >
      <div className="fs-eyebrow">YOUR SAVED TEMPLATES</div>
      <h2>Reuse your best setups.</h2>
      <p className="fs-body">
        Named snapshots of the workflows and creative choices you want to use
        again.
      </p>
      {project ? (
        <CaptureTemplate
          key={project.id}
          project={project}
          busy={busy}
          save={save}
        />
      ) : (
        <p className="fs-hint">
          Open a project to save its setup as a template.
        </p>
      )}
      <p className="fs-hint">
        Reference files need to be reattached. Generation results, completed
        approvals, budget history and observed model capabilities stay with
        their original project.
      </p>
      {templates.length ? (
        templates.map((t) => (
          <TemplateRow
            key={t.id}
            template={t}
            project={project}
            busy={busy}
            save={save}
            onNew={onNew}
          />
        ))
      ) : (
        <div className="cv-template-empty">
          Your saved templates will appear here.
        </div>
      )}
    </section>
  );
}
