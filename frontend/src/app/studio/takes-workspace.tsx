"use client";
import {MediaUpload,ImportCostReport} from "./media-upload";
import { useMemo, useState } from "react";
import { studioApi as api } from "./client";
import { DraftNotice, Field, useDraft } from "./creative-forms";
import type { Project, Asset, Job, Save } from "./creative-types";

function Media({ asset }: { asset: Asset | undefined }) {
  return (
    <div className="cv-take-media">
      {!asset ? (
        <p>Choose a real take</p>
      ) : asset.kind === "image" ? (
        <img src={asset.url} alt={asset.name || "Returned image take"} />
      ) : (
        <video src={asset.url} controls preload="metadata" />
      )}
    </div>
  );
}

function Inspection({
  project,
  asset,
  busy,
  save,
}: {
  project: Project;
  asset: Asset;
  busy: boolean;
  save: Save;
}) {
  const required = useMemo(
    () => asset.required_checks || [],
    [asset.required_checks],
  );
  const initial = useMemo(
    () => ({
      criteria:
        asset.review?.criteria ||
        Object.fromEntries(required.map((c) => [c, false])),
      notes: asset.review?.notes || "",
      defect: asset.review?.defect || "",
      inspected: asset.review?.inspected || [],
    }),
    [asset.review, required],
  );
  const form = useDraft(
      initial,
      project.revision,
      `inspection:${project.id}:${asset.id}`,
    ),
    r = form.draft;
  const segments =
    asset.kind === "image" ? ["image"] : ["beginning", "middle", "end"];
  return (
    <div className="cv-section">
      <h2>Inspect this take</h2>
      <p className="fs-body">
        Watch the full clip, including late seconds. Record only what you
        actually inspected.
      </p>
      <DraftNotice {...form} />
      {segments.map((s) => (
        <label className="fs-policy cv-check-option" key={s}>
          <input
            type="checkbox"
            checked={r.inspected.includes(s)}
            onChange={(e) =>
              form.edit((v) => ({
                ...v,
                inspected: e.target.checked
                  ? [...v.inspected, s]
                  : v.inspected.filter((x) => x !== s),
              }))
            }
          />
          Inspected {s}
        </label>
      ))}
      <div className="cv-criteria">
        {required.map((c) => (
          <label className="fs-policy cv-check-option" key={c}>
            <input
              type="checkbox"
              checked={!!r.criteria[c]}
              onChange={(e) =>
                form.edit((v) => ({
                  ...v,
                  criteria: { ...v.criteria, [c]: e.target.checked },
                }))
              }
            />
            {c}
          </label>
        ))}
      </div>
      <Field
        label="Inspection notes"
        multiline
        value={r.notes}
        onChange={(notes) => form.edit((v) => ({ ...v, notes }))}
      />
      <Field
        label="Named defect / revision target"
        multiline
        value={r.defect}
        onChange={(defect) => form.edit((v) => ({ ...v, defect }))}
      />
      <button
        className="fs-button"
        disabled={busy || !form.dirty || form.conflict}
        onClick={() =>
          save(async () => {
            await api("record_take_review", {
              project_id: project.id,
              asset_id: asset.id,
              review: r,
              expected_revision: form.revision,
            });
            form.saved();
          })
        }
      >
        Save inspection evidence
      </button>
      {asset.review && (
        <p className="fs-hint">
          Last recorded by {asset.review.actor} ·{" "}
          {new Date(asset.review.at).toLocaleString()}. This is evidence, not a
          workflow approval.
        </p>
      )}
    </div>
  );
}

function CostReport({
  project,
  job,
  busy,
  save,
}: {
  project: Project;
  job: Job;
  busy: boolean;
  save: Save;
}) {
  const initial = useMemo(
    () => ({
      actual: job.cost?.actual ?? null,
      evidence: job.cost?.evidence || "",
    }),
    [job.cost],
  );
  const form = useDraft(
    initial,
    project.revision,
    `cost:${project.id}:${job.id}`,
  );
  return (
    <details className="cv-cost-report">
      <summary>
        {job.kind} · {job.status.replaceAll("_", " ")} · planned{" "}
        {job.cost?.planned ?? "unknown"} / actual{" "}
        {job.cost?.actual ?? "unknown"} {job.cost?.unit}
      </summary>
      <DraftNotice {...form} />
      <Field
        label={`Actual cost ${job.id.slice(0, 6)}`}
        type="number"
        value={form.draft.actual ?? ""}
        onChange={(v) =>
          form.edit((old) => ({ ...old, actual: v === "" ? null : Number(v) }))
        }
      />
      <Field
        label={`Cost evidence ${job.id.slice(0, 6)}`}
        value={form.draft.evidence}
        onChange={(evidence) => form.edit((old) => ({ ...old, evidence }))}
      />
      <button
        className="fs-button"
        disabled={
          busy ||
          form.draft.actual === null ||
          !form.draft.evidence.trim() ||
          form.conflict ||
          !form.dirty
        }
        onClick={() =>
          save(async () => {
            await api("record_job_cost", {
              project_id: project.id,
              job_id: job.id,
              ...form.draft,
              expected_revision: form.revision,
            });
            form.saved();
          })
        }
      >
        Record actual cost
      </button>
    </details>
  );
}

export function TakesWorkspace({
  project,
  busy,
  save,
}: {
  project: Project;
  busy: boolean;
  save: Save;
}) {
  const [shotId, setShotId] = useState(
    project.next_action.shot_id || project.shots[0]?.id || "",
  );
  const currentShotIds = new Set(project.shots.map((s) => s.id));
  const earlierTakes = project.assets.filter((a) => a.shot_id && !currentShotIds.has(a.shot_id) && !a.role);
  const earlierPlan = shotId === "__earlier_plan__" || !currentShotIds.has(shotId);
  const takes = earlierPlan ? earlierTakes : project.assets.filter((a) => a.shot_id === shotId && !a.role);
  const [selected, setSelected] = useState(""),
    [compare, setCompare] = useState(""),
    [reason, setReason] = useState(""),
    [repair, setRepair] = useState<unknown>(null),
    [repairError, setRepairError] = useState(""),
    [mask, setMask] = useState("");
  const asset =
    takes.find((a) => a.id === selected) ||
    takes.findLast((a) => !a.stale) ||
    takes.at(-1);
  const second = takes.find((a) => a.id === compare);
  const shot = project.shots.find((s) => s.id === shotId);
  return (
    <section>
      <div className="fs-eyebrow">MEDIA, EVIDENCE & ITERATION</div>
      <h1>Takes & quality</h1>
      <p className="fs-lead">
        Compare real outputs, name a defect and revise the affected shot.
        Previous files remain available.
      </p>
      <MediaUpload project={project} busy={busy} save={save}/>
      <label className="fs-label">
        Shot
        <select
          value={earlierPlan ? "__earlier_plan__" : shotId}
          onChange={(e) => {
            setShotId(e.target.value);
            setSelected("");
            setCompare("");
            setRepair(null);
          }}
        >
          {project.shots.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
          {earlierTakes.length > 0 && <option value="__earlier_plan__">Earlier plan media ({earlierTakes.length})</option>}
        </select>
      </label>
      <div className="cv-take-list">
        {takes.length === 0 ? (
          <p className="fs-body">No media has been returned for this shot.</p>
        ) : (
          takes.map((a, i) => (
            <button
              className={`fs-button ${asset?.id === a.id ? "cv-take-active" : ""}`}
              key={a.id}
              onClick={() => {
                setSelected(a.id);
                setRepair(null);
              }}
            >
              Take {i + 1} · {a.kind}{" "}
              {a.id ===
              (a.kind === "image" ? shot?.image_asset : shot?.video_asset)
                ? "· selected"
                : a.stale
                  ? "· earlier revision"
                  : ""}
            </button>
          ))
        )}
      </div>
      {asset && (
        <>
          <div className="cv-comparison">
            <div>
              <div className="cv-section-heading">
                <span>INSPECTING · {asset.id.slice(0, 8)}</span>
                {!earlierPlan && <button
                  className="fs-link"
                  disabled={busy}
                  onClick={() =>
                    save(() =>
                      api("select_take", {
                        project_id: project.id,
                        asset_id: asset.id,
                        expected_revision: project.revision,
                      }),
                    )
                  }
                >
                  Select this take
                </button>}
              </div>
              <Media asset={asset} />
            </div>
            <div>
              <label className="fs-label">
                Compare with
                <select
                  value={compare}
                  onChange={(e) => setCompare(e.target.value)}
                >
                  <option value="">Choose another take</option>
                  {takes
                    .filter((a) => a.id !== asset.id)
                    .map((a, i) => (
                      <option key={a.id} value={a.id}>
                        Take {i + 1} · {a.kind} · {a.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
              </label>
              <Media asset={second} />
            </div>
          </div>
          <p className="fs-path">{asset.path}</p>
          {earlierPlan && <p className="fs-body">This take belongs to a replaced shot plan. <a href={asset.url} download>Download original</a> to reuse it through Import media on a current shot.</p>}
          <ImportCostReport key={`cost-${asset.id}`} project={project} asset={asset} busy={busy} save={save}/>
          {!earlierPlan && <Inspection
            key={asset.id}
            project={project}
            asset={asset}
            busy={busy}
            save={save}
          />}
          {!earlierPlan && <div className="cv-section">
            <h2>Targeted revision</h2>
            <Field
              label="What needs to change?"
              multiline
              value={reason}
              onChange={setReason}
            />
            <div className="fs-actions">
              <button
                className="fs-primary"
                disabled={busy || !reason.trim()}
                onClick={() =>
                  save(() =>
                    api("revise_shot", {
                      project_id: project.id,
                      shot_id: shotId,
                      kind: asset.kind,
                      reason,
                      expected_revision: project.revision,
                    }),
                  )
                }
              >
                Request a new {asset.kind} take
              </button>
              {asset.kind === "video" && (
                <button
                  className="fs-button"
                  disabled={busy || asset.stale}
                  onClick={() =>
                    save(() =>
                      api("extract_continuation", {
                        project_id: project.id,
                        asset_id: asset.id,
                        expected_revision: project.revision,
                      }),
                    )
                  }
                >
                  Extract continuation frame
                </button>
              )}
            </div>
            <p className="fs-hint">
              Update direction when needed, then follow the workflow for a new
              handoff. Budget and approval rules still apply. Extracted frames
              must be inspected and explicitly bound to the next shot.
            </p>
            {asset.kind === "image" && (
              <>
                <label className="fs-label">
                  Repair mask (optional)
                  <select
                    value={mask}
                    onChange={(e) => setMask(e.target.value)}
                  >
                    <option value="">No mask supplied</option>
                    {project.assets
                      .filter((a) => a.kind === "image" && a.id !== asset.id)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name || a.id.slice(0, 8)}
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  className="fs-button"
                  disabled={busy || !reason.trim()}
                  onClick={async () => {
                    setRepairError("");
                    try {
                      setRepair(
                        await api("repair_handoff", {
                          project_id: project.id,
                          asset_id: asset.id,
                          defect: reason,
                          mask_asset_id: mask,
                          expected_revision: project.revision,
                        }),
                      );
                    } catch (e) {
                      setRepairError((e as Error).message);
                    }
                  }}
                >
                  Prepare image-repair handoff
                </button>
                {repairError && <p role="alert">{repairError}</p>}
                {repair !== null && (
                  <label className="fs-label">
                    External repair brief
                    <textarea
                      aria-label="Image repair handoff"
                      readOnly
                      rows={12}
                      value={JSON.stringify(repair, null, 2)}
                    />
                  </label>
                )}
              </>
            )}
          </div>}
        </>
      )}
      <div className="cv-section">
        <h2>Attempt costs</h2>
        <p className="fs-body">
          Reservations remain until an actual cost is reported. A canceled
          handoff does not establish a provider refund.
        </p>
        {project.jobs
          .filter((j) => j.shot_id === shotId)
          .map((j) => (
            <CostReport
              key={j.id}
              project={project}
              job={j}
              busy={busy}
              save={save}
            />
          ))}
      </div>
    </section>
  );
}
