"use client";
import { useEffect, useState } from "react";
import { ArrowRight, Layers } from "lucide-react";
import { studioApi as api } from "./client";
import type { Project, Save } from "./creative-types";

type Role = {
  id: string;
  title: string;
  coverage_role: string;
  purpose: string;
  weight: number;
  transition_in: string;
  audio_continuity: string;
  source_role_id?: string;
};
type Sequence = {
  id: string;
  name: string;
  description: string;
  roles: Role[];
  technique_notes: string[];
};
type Allocated = {
  title: string;
  duration_seconds: number;
  edit_duration_seconds?: number;
  direction: {
    editorial: {
      coverage_role: string;
      purpose?: string;
      transition_in?: string;
      audio_continuity?: string;
    };
  };
};
type Preview = {
  source_revision: number;
  sequence_id: string;
  roles: Allocated[];
  shot_count: number;
  replacement_required: boolean;
  existing_work: { shots: number; assets: number; documents: number };
};

export function SequenceWorkspace({
  project,
  busy,
  save,
}: {
  project: Project;
  busy: boolean;
  save: Save;
}) {
  const [catalogue, setCatalogue] = useState<Sequence[]>([]),
    [selected, setSelected] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null),
    [confirmed, setConfirmed] = useState(false),
    [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const imageOnly = project.output_type === "image";
  useEffect(() => {
    if (imageOnly) return;
    let active = true;
    api<{ sequences: Sequence[] }>("sequence_catalog")
      .then((data) => {
        if (active) {
          setCatalogue(data.sequences);
          setSelected((value) => value || data.sequences[0]?.id || "");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [imageOnly, retry]);
  useEffect(() => {
    if (imageOnly || !selected) return;
    let active = true;
    setPreview(null);
    setConfirmed(false);
    setError("");
    api<Preview>("preview_sequence", {
      project_id: project.id,
      sequence_id: selected,
    })
      .then((data) => {
        if (active) setPreview(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [imageOnly, project.id, project.revision, selected, retry]);
  if (imageOnly)
    return (
      <section className="cv-section">
        <h2>Image composition</h2>
        <p>
          Video sequence patterns are for video projects. Shape this image in
          Composition & direction.
        </p>
      </section>
    );
  const sequence = catalogue.find((value) => value.id === selected);
  const ready =
    preview?.source_revision === project.revision &&
    preview.sequence_id === selected;
  return (
    <section
      className="os-sequence-workspace"
      aria-label="Video sequence planner"
    >
      <div className="os-library-heading">
        <div>
          <div className="fs-eyebrow">PLAN / COVERAGE</div>
          <h2>Sequence plan</h2>
          <p className="fs-body">
            Give each shot a role. Connect the pictures, message and sound.
          </p>
        </div>
        <Layers size={25} aria-hidden="true" />
      </div>
      {error && (
        <p role="alert">
          {error}{" "}
          <button
            className="fs-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry sequence preview
          </button>
        </p>
      )}
      <div className="os-sequence-layout">
        <nav aria-label="Sequence pattern">
          {catalogue.map((value) => (
            <button
              key={value.id}
              aria-pressed={value.id === selected}
              className={value.id === selected ? "active" : ""}
              onClick={() => setSelected(value.id)}
            >
              {value.name}
              <ArrowRight size={14} />
            </button>
          ))}
        </nav>
        <div className="os-sequence-detail">
          {sequence ? (
            <>
              <h3>{sequence.name}</h3>
              <p className="fs-body">{sequence.description}</p>
              <ol className="os-sequence-roles">
                {sequence.roles.map((role, index) => (
                  <li key={role.id}>
                    <span className="os-sequence-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <small>{role.coverage_role.replaceAll("_", " ")}</small>
                      <h4>{role.title}</h4>
                      <p>{role.purpose}</p>
                      <dl>
                        <dt>Transition</dt>
                        <dd>{role.transition_in}</dd>
                        <dt>Sound</dt>
                        <dd>{role.audio_continuity}</dd>
                      </dl>
                    </div>
                  </li>
                ))}
              </ol>
              <details className="os-sequence-notes">
                <summary>Why this sequence works</summary>
                <ul>
                  {sequence.technique_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </details>
              {preview ? (
                <section
                  className="os-sequence-preview"
                  aria-label="Allocated shot preview"
                >
                  <h4>
                    Your {project.settings.duration_seconds}s plan ·{" "}
                    {preview.shot_count} shots
                  </h4>
                  <ol>
                    {preview.roles.map((role, index) => (
                      <li key={index}>
                        <span>{role.title}</span>
                        <strong>
                          {Number(
                            (
                              role.edit_duration_seconds ??
                              role.duration_seconds
                            ).toFixed(1),
                          )}
                          s
                        </strong>
                      </li>
                    ))}
                  </ol>
                  {preview.replacement_required && (
                    <label className="fs-policy">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(event) => setConfirmed(event.target.checked)}
                      />
                      <span>
                        Replace the current {project.shots.length}-shot plan.
                        Existing files are retained; selections and dependent
                        reviews reopen.
                      </span>
                    </label>
                  )}
                  <button
                    className="fs-primary"
                    disabled={
                      busy ||
                      !ready ||
                      (preview.replacement_required && !confirmed)
                    }
                    onClick={() =>
                      save(async () => {
                        await api("apply_sequence", {
                          project_id: project.id,
                          sequence_id: selected,
                          expected_revision: preview.source_revision,
                          confirm_replace: confirmed,
                        });
                        setConfirmed(false);
                      })
                    }
                  >
                    Apply sequence
                  </button>
                </section>
              ) : (
                !error && <p role="status">Preparing shot allocation…</p>
              )}
              <p className="fs-hint">
                These are editable coverage and editing instructions. J-cuts and
                L-cuts describe sound continuity for your editor; Orchestra does
                not assemble or render the final cut.
              </p>
            </>
          ) : (
            !error && <p role="status">Loading sequence patterns…</p>
          )}
        </div>
      </div>
    </section>
  );
}
