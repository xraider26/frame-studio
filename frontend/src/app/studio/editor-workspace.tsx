"use client";
import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { studioApi as api } from "./client";
import type { Project } from "./creative-types";

type EditShot = {
  id: string;
  title: string;
  timeline_in: number;
  timeline_out: number;
  source_in: number;
  source_out: number;
  video: { path: string } | null;
  narration: string;
};
type Handoff = {
  shots: EditShot[];
  edit_duration_seconds: number;
  ready: boolean;
};
type Bundle = {
  download_url: string;
  manifest: { warnings: string[]; ready: boolean; source_revision: number };
};
export function EditorWorkspace({
  project,
  onRecord,
}: {
  project: Project;
  onRecord: () => void;
}) {
  const [plan, setPlan] = useState<Handoff | null>(null),
    [storedBundle, setBundle] = useState<Bundle | null>(null),
    [error, setError] = useState(""),
    [preparing, setPreparing] = useState(false);
  useEffect(() => {
    let canceled = false;
    api<Handoff>("editor_handoff", { project_id: project.id })
      .then((value) => {
        if (!canceled) {
          setPlan(value);
          setError("");
        }
      })
      .catch((e) => {
        if (!canceled) setError(e.message);
      });
    return () => {
      canceled = true;
    };
  }, [project.id, project.revision]);
  const bundle =
    storedBundle?.manifest.source_revision === project.revision
      ? storedBundle
      : null;
  return (
    <section>
      <div className="fs-eyebrow">EXTERNAL EDITING</div>
      <h1>Editor handoff</h1>
      <p className="fs-lead">
        Selected takes, retained timing, dialogue, sound and caption directions
        for your preferred editor.
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="cv-edit-table">
        <table>
          <thead>
            <tr>
              <th>Shot</th>
              <th>Edit range</th>
              <th>Source range</th>
              <th>Selected media</th>
            </tr>
          </thead>
          <tbody>
            {plan?.shots.map((s) => (
              <tr key={s.id}>
                <td>{s.title}</td>
                <td>
                  {s.timeline_in}s → {s.timeline_out}s
                </td>
                <td>
                  {s.source_in}s → {s.source_out}s
                </td>
                <td>
                  {s.video ? <code>{s.video.path}</code> : "No selected video"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fs-hint">
        {plan?.edit_duration_seconds}s retained ·{" "}
        {plan?.ready
          ? "Production workflow cleared"
          : "Production workflow still has outstanding steps"}
        . Package preparation does not render an edit.
      </p>
      <div className="fs-actions">
        <button
          className="fs-primary"
          disabled={preparing}
          onClick={async () => {
            setPreparing(true);
            setError("");
            try {
              setBundle(
                await api("export_editor_package", { project_id: project.id }),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setPreparing(false);
            }
          }}
        >
          <Download size={14} />
          {preparing ? "Preparing local files…" : "Prepare editor package"}
        </button>
        <button className="fs-button" onClick={onRecord}>
          Record editor handoff
        </button>
      </div>
      {bundle && (
        <div className="cv-section">
          <a
            className="fs-primary"
            href={bundle.download_url}
            download="studio-editor-handoff.zip"
          >
            Download editor ZIP
          </a>
          <p className="fs-hint">
            Contains editor-manifest.json, edit-decision.csv and available
            selected MP4s. This is not a native editor project.
          </p>
          {bundle.manifest.warnings.map((w, i) => (
            <p className="fs-hint" key={i}>
              {w}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
