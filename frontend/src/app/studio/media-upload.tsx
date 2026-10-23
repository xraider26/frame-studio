"use client";
import { useRef, useState } from "react";
import type { Asset, Project, Save } from "./creative-types";
import { studioApi } from "./client";
import { DraftNotice, useDraft } from "./creative-forms";
import { useMemo } from "react";

export function ImportCostReport({
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
  const source = useMemo(
    () => ({
      actual: asset.cost?.actual == null ? "" : String(asset.cost.actual),
      evidence: asset.cost?.evidence || "",
    }),
    [asset.cost],
  );
  const form = useDraft(
    source,
    project.revision,
    `import-cost:${project.id}:${asset.id}`,
  );
  if (asset.provenance?.type !== "externally_created") return null;
  const actual = Number(form.draft.actual);
  return (
    <section className="cv-section">
      <h3>Externally created take</h3>
      <p className="fs-hint">
        Imported independently of a studio generation job. Its cost stays
        unknown until you record it with evidence.
      </p>
      <DraftNotice {...form} />
      <label className="fs-label">
        Actual imported cost (
        {asset.cost?.unit ||
          project.production?.resources.unit ||
          "project units"}
        )
        <input
          type="number"
          min="0"
          step="any"
          value={form.draft.actual}
          onChange={(e) => form.edit((v) => ({ ...v, actual: e.target.value }))}
        />
      </label>
      <label className="fs-label">
        Cost evidence
        <textarea
          value={form.draft.evidence}
          onChange={(e) =>
            form.edit((v) => ({ ...v, evidence: e.target.value }))
          }
        />
      </label>
      <button
        className="fs-button"
        disabled={
          busy ||
          form.conflict ||
          !form.draft.actual.trim() ||
          !Number.isFinite(actual) ||
          actual < 0 ||
          !form.draft.evidence.trim()
        }
        onClick={() =>
          save(async () => {
            await studioApi("record_import_cost", {
              project_id: project.id,
              asset_id: asset.id,
              actual,
              evidence: form.draft.evidence,
              expected_revision: form.revision,
            });
            form.saved();
          })
        }
      >
        Record imported take cost
      </button>
    </section>
  );
}
export function MediaUpload({
  project,
  busy,
  save,
  entityId,
  disabled = false,
}: {
  project: Project;
  busy: boolean;
  save: Save;
  entityId?: string;
  disabled?: boolean;
}) {
  const [role, setRole] = useState(entityId ? "reference" : "take"),
    [shot, setShot] = useState(project.shots[0]?.id || ""),
    [generator, setGenerator] = useState(""),
    [prompt, setPrompt] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const imageOnly = !!entityId || project.output_type === "image";
  function pick(f: File | undefined) {
    if (!f) return;
    if (
      !f.type.startsWith("image/") &&
      (!f.type.startsWith("video/") || imageOnly)
    ) {
      setError(
        imageOnly ? "Choose an image file." : "Choose an image or video file.",
      );
      return;
    }
    setFile(f);
    setError("");
  }
  return (
    <div
      className="cv-media-upload"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (!busy && !disabled) pick(e.dataTransfer.files[0]);
      }}
    >
      <h3>{entityId ? "Upload entity reference" : "Import external media"}</h3>
      <p className="fs-hint">
        {project.output_type === "image" && !entityId
          ? "Select an image take, then complete final review. "
          : ""}
        Choose a file or drop it here.{" "}
        {disabled ? "Apply bible changes before uploading to this entity." : ""}
      </p>
      <label className="fs-label">
        {entityId ? "Reference image file" : "Media file"}
        <input
          ref={input}
          type="file"
          disabled={busy || disabled}
          accept={imageOnly ? "image/*" : "image/*,video/*"}
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </label>
      {file && <p>{file.name}</p>}
      {!entityId && (
        <>
          <label className="fs-label">
            Media role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="reference">Reference</option>
              <option value="take">Shot take</option>
              {project.output_type !== "image" && (
                <option value="final">Final</option>
              )}
            </select>
          </label>
          {role === "take" && (
            <label className="fs-label">
              Target shot
              <select value={shot} onChange={(e) => setShot(e.target.value)}>
                {project.shots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="fs-label">
            Generator (optional)
            <input
              value={generator}
              onChange={(e) => setGenerator(e.target.value)}
            />
          </label>
          <label className="fs-label">
            Prompt (optional)
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      <button
        className="fs-button"
        disabled={busy || disabled || !file || (role === "take" && !shot)}
        onClick={() =>
          save(async () => {
            const data = new FormData();
            data.set("file", file!);
            data.set("project_id", project.id);
            data.set("expected_revision", String(project.revision));
            data.set("role", role);
            data.set(
              "kind",
              file!.type.startsWith("video/") ? "video" : "image",
            );
            data.set("name", file!.name);
            if (entityId) data.set("entity_id", entityId);
            if (role === "take") data.set("shot_id", shot);
            data.set("generator", generator);
            data.set("prompt", prompt);
            const res = await fetch("/api/studio/upload", {
              method: "POST",
              body: data,
            });
            const value = await res.json();
            if (!res.ok)
              throw new Error(value.message || value.detail || "Upload failed");
            setFile(null);
            if (input.current) input.current.value = "";
          })
        }
      >
        Upload {entityId ? "reference" : role === "take" ? "shot take" : role}
      </button>
    </div>
  );
}
