"use client";
import { useState } from "react";
import { studioApi as api } from "./client";
import { DraftNotice, useDraft } from "./creative-forms";
import type { Project, Save } from "./creative-types";
import type { SavedTemplate } from "./template-workspace";

type Evidence = {
  id: string;
  level: "pilot" | "production";
  actor: string;
  at: string;
  note: string;
  project_id: string;
  project_revision: number;
  snapshot_hash?: string;
  scope: string;
  assets: { id: string; kind: string; shot_id: string }[];
};
type RecipeMetrics = {
  template_id: string;
  template_revision: number;
  snapshot_hash: string | null;
  source_project_id: string | null;
  source_project_revision: number | null;
  settings_shot_id: string;
  usage_count: number;
  observed_defects: number;
  scope: string;
  projects: {
    id: string;
    name: string;
    revision: number;
    source: boolean;
    deleted?: boolean;
    attempts: number;
    selected_video_shots: number;
    observed_defects: number;
  }[];
  costs: {
    unit: string;
    reported_actual: number;
    planned_unsettled: number;
    unknown_actual_jobs: number;
    unknown_exposure_jobs: number;
  }[];
  evidence: Evidence[];
};
const initialEvidence = { note: "", level: "pilot" };

export function RecipeEvidence({
  template,
  project,
  busy,
  save,
}: {
  template: SavedTemplate;
  project: Project | null;
  busy: boolean;
  save: Save;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<RecipeMetrics | null>(null);
  const [error, setError] = useState("");
  const form = useDraft(
    initialEvidence,
    project?.revision || 0,
    "recipe-evidence:" + template.id + ":" + (project?.id || "none"),
  );
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setMetrics(
        await api<RecipeMetrics>("recipe_metrics", {
          template_id: template.id,
        }),
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load recipe evidence.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div>
      <button
        className="fs-link"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
          if (!open) void refresh();
        }}
      >
        Recipe evidence &amp; usage
      </button>
      {open && (
        <div
          className="cv-template-panel"
          aria-label={`Evidence for ${template.name}`}
        >
          <h3>Observed recipe outcomes</h3>
          {loading && <p role="status">Loading recipe evidence…</p>}
          {error && <p role="alert">{error}</p>}
          {metrics && (
            <>
              <p className="fs-body">
                {metrics.usage_count} projects used this recipe ·{" "}
                {metrics.observed_defects} recorded defect observations.
              </p>
              <p className="fs-hint">{metrics.scope}</p>
              {metrics.source_project_id && (
                <p className="fs-hint">
                  Captured from {metrics.source_project_id} · revision{" "}
                  {metrics.source_project_revision}
                  {metrics.settings_shot_id
                    ? ` · look from shot ${metrics.settings_shot_id}`
                    : ""}
                  .
                </p>
              )}
              {metrics.costs.length ? (
                metrics.costs.map((c) => (
                  <p className="fs-hint" key={c.unit}>
                    {c.unit}: {c.reported_actual} reported actual ·{" "}
                    {c.planned_unsettled} planned and unsettled ·{" "}
                    {c.unknown_actual_jobs} jobs with actual cost unknown ·{" "}
                    {c.unknown_exposure_jobs} jobs with no known cost or
                    reservation.
                  </p>
                ))
              ) : (
                <p className="fs-hint">
                  No generation jobs recorded for this recipe yet.
                </p>
              )}
              {metrics.projects.length > 0 && (
                <details>
                  <summary>Source and usage projects</summary>
                  <ul>
                    {metrics.projects.map((p) => (
                      <li key={p.id}>
                        {p.name}
                        {p.source ? " (recipe source)" : ""}
                        {p.deleted ? " (in Trash)" : ""} · {p.id} · revision{" "}
                        {p.revision} · {p.attempts} attempts ·{" "}
                        {p.selected_video_shots} selected video shots ·{" "}
                        {p.observed_defects} defect observations
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {metrics.evidence.length ? (
                metrics.evidence.map((e) => (
                  <div key={e.id}>
                    <h4>{e.level} endorsement</h4>
                    <p className="fs-body">{e.note}</p>
                    <p className="fs-hint">
                      Human ({e.actor}) · {e.at} · {e.project_id} · revision{" "}
                      {e.project_revision}
                    </p>
                    <p className="fs-hint">
                      {e.scope}. Assets:{" "}
                      {e.assets.map((a) => `${a.kind} ${a.id}`).join(", ")}.
                    </p>
                    <details>
                      <summary>Recorded recipe identity</summary>
                      <code>{e.snapshot_hash}</code>
                    </details>
                  </div>
                ))
              ) : (
                <p className="fs-hint">
                  No human endorsement. This saved setup has no recorded
                  evidence of successful output.
                </p>
              )}
              {project ? (
                <>
                  <h4>Endorse inspected output from {project.name}</h4>
                  <p className="fs-hint">
                    Pilot requires the first selected video and any source-look
                    shot. Production requires every selected shot video.
                    Selected images also need full checks. The app checks actual
                    files, compatible inputs, complete inspections and every
                    quality criterion. Production evidence covers shot output;
                    final editing and delivery are outside this endorsement.
                  </p>
                  <DraftNotice {...form} />
                  <label className="fs-label">
                    Evidence level
                    <select
                      value={form.draft.level}
                      onChange={(e) =>
                        form.edit((v) => ({ ...v, level: e.target.value }))
                      }
                    >
                      <option value="pilot">Reviewed pilot</option>
                      <option value="production">
                        Reviewed production shots
                      </option>
                    </select>
                  </label>
                  <label className="fs-label">
                    Human review note
                    <textarea
                      aria-label="Human review note"
                      value={form.draft.note}
                      maxLength={8000}
                      placeholder="What did you inspect, what worked, and what remains untested?"
                      onChange={(e) =>
                        form.edit((v) => ({ ...v, note: e.target.value }))
                      }
                    />
                  </label>
                  <button
                    className="fs-button"
                    disabled={
                      busy ||
                      loading ||
                      form.conflict ||
                      !metrics.snapshot_hash ||
                      !form.draft.note.trim()
                    }
                    onClick={() =>
                      save(async () => {
                        setError("");
                        try {
                          setMetrics(
                            await api<RecipeMetrics>("endorse_recipe", {
                              template_id: template.id,
                              project_id: project.id,
                              note: form.draft.note,
                              expected_revision: form.revision,
                              template_revision: metrics.template_revision,
                              level: form.draft.level,
                            }),
                          );
                          form.saved();
                        } catch (e) {
                          setError(
                            e instanceof Error
                              ? e.message
                              : "Could not record recipe evidence.",
                          );
                        }
                      })
                    }
                  >
                    Record human endorsement
                  </button>
                  {!metrics.snapshot_hash && (
                    <p className="fs-hint">
                      This legacy template can still be reused. Capture a new
                      recipe to record source-backed evidence.
                    </p>
                  )}
                </>
              ) : (
                <p className="fs-hint">
                  Open the inspected project to record human endorsement.
                </p>
              )}
            </>
          )}
          <button
            className="fs-link"
            disabled={loading}
            onClick={() => void refresh()}
          >
            Refresh recipe evidence
          </button>
        </div>
      )}
    </div>
  );
}
