"use client";

import { useMemo, useState } from "react";
import { Download, ArrowRight } from "lucide-react";
import { studioApi } from "./client";
import { DraftNotice, useDraft } from "./creative-forms";
import { Checks } from "./creative-workspace";
import type { Project } from "./creative-types";

type Profile = { id: string; name: string; hint: string; source?: string };
type Props = {
  project: Project;
  videoProfiles: Profile[];
  imageProfiles: Profile[];
  busy: boolean;
  save: (fn: () => Promise<unknown>) => Promise<void>;
};

export function GeneratorExport({
  project,
  videoProfiles,
  imageProfiles,
  busy,
  save,
}: Props) {
  const savedSettings = useMemo(
    () =>
      Object.fromEntries(
        [
          "generation_mode",
          "video_generator",
          "image_generator",
          "custom_video_template",
          "custom_image_template",
        ].map((k) => [k, project.settings[k]]),
      ),
    [project.settings],
  );
  const form = useDraft(
    savedSettings,
    project.revision,
    "generator:" + project.id,
  );
  const settings = form.draft;
  const dirty = form.dirty;
  const [bundle, setBundle] = useState<{
    source_revision: number;
    markdown: string;
    download_url: string;
  } | null>(null);
  const [error, setError] = useState("");
  function change(key: string, value: string) {
    form.edit((s) => ({ ...s, [key]: value }));
    setBundle(null);
  }
  const video = videoProfiles.find((v) => v.id === settings.video_generator);
  const image = imageProfiles.find((v) => v.id === settings.image_generator);
  return (
    <section>
      <div className="fs-eyebrow">GENERATOR HANDOFF</div>
      <h1>Ready for the generator you use.</h1>
      <p className="fs-lead">
        Choose the generator’s prompt profile. Export a portable package for
        your agent, or use the same prompts through a connected API.
      </p>
      <DraftNotice {...form} />
      <div className="fs-generator-controls">
        <div className="fs-form-grid">
          <label className="fs-label">
            Generation route
            <select
              value={settings.generation_mode}
              onChange={(e) => change("generation_mode", e.target.value)}
            >
              <option value="external_agent">
                External agent / export · no API required
              </option>
              <option value="api">Connected API generator</option>
            </select>
          </label>
          <label className="fs-label">
            Video generator template
            <select
              value={settings.video_generator}
              onChange={(e) => change("video_generator", e.target.value)}
            >
              {videoProfiles.map((v) => (
                <option value={v.id} key={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label className="fs-label">
            Image generator template
            <select
              value={settings.image_generator}
              onChange={(e) => change("image_generator", e.target.value)}
            >
              {imageProfiles.map((v) => (
                <option value={v.id} key={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="fs-body">{video?.hint}</p>
        <p className="fs-hint">{image?.hint}</p>
        {video?.source && (
          <a
            className="fs-link"
            href={video.source}
            target="_blank"
            rel="noreferrer"
          >
            Generator prompting guide ↗
          </a>
        )}
        {settings.video_generator === "custom" && (
          <label className="fs-label">
            Custom video prompt template
            <textarea
              rows={4}
              value={settings.custom_video_template}
              onChange={(e) => change("custom_video_template", e.target.value)}
            />
          </label>
        )}
        {settings.image_generator === "custom" && (
          <label className="fs-label">
            Custom image prompt template
            <textarea
              rows={4}
              value={settings.custom_image_template}
              onChange={(e) => change("custom_image_template", e.target.value)}
            />
          </label>
        )}
        {(settings.video_generator === "custom" ||
          settings.image_generator === "custom") && (
          <p className="fs-hint">
            Supported placeholders:{" "}
            {
              "{subject} {motion} {camera} {lighting} {style} {palette} {framing} {lens} {continuity} {narration} {sound} {aspect_ratio} {duration} {environment} {mood} {opening} {ending} {dialogue} {composition} {body_look} {state_before} {state_after} {references}"
            }
          </p>
        )}
        <button
          className="fs-button"
          disabled={busy || !dirty || form.conflict}
          onClick={() =>
            save(async () => {
              const fields = [
                "generation_mode",
                "video_generator",
                "image_generator",
                "custom_video_template",
                "custom_image_template",
              ];
              await studioApi("update_settings", {
                project_id: project.id,
                settings: Object.fromEntries(
                  fields.map((k) => [k, settings[k]]),
                ),
                expected_revision: form.revision,
              });
              form.saved();
            })
          }
        >
          Apply generator choices <ArrowRight size={14} />
        </button>
        <p className="fs-hint">
          Changing profiles updates prompts and reopens affected outputs and
          reviews. The profile does not connect an account.
        </p>
      </div>
      <Checks checks={project.preflight} shots={project.shots} />
      <div className="fs-export-section">
        <div className="fs-eyebrow">PORTABLE GENERATION PACKAGE</div>
        <h2>One file to hand to your agent.</h2>
        <p className="fs-body">
          A ZIP containing <code>manifest.json</code>, <code>prompts.md</code>,{" "}
          <code>README.txt</code>, and available reference images or motion
          videos. Shot IDs and the review policy travel with it. Your agent
          returns the real results through MCP.
        </p>
        {error && (
          <p role="alert" className="fs-body">
            {error}
          </p>
        )}
        <button
          className="fs-primary"
          disabled={busy || dirty}
          onClick={async () => {
            setError("");
            try {
              setBundle({
                ...(await studioApi<{ markdown: string; download_url: string }>(
                  "export_handoff",
                  { project_id: project.id },
                )),
                source_revision: project.revision,
              });
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          <Download size={14} /> Prepare export package
        </button>
        {bundle && bundle.source_revision === project.revision && !dirty && (
          <div className="fs-export-ready">
            <a
              className="fs-primary"
              href={bundle.download_url}
              download="studio-generator-handoff.zip"
            >
              <Download size={14} /> Download handoff ZIP
            </a>
            <p className="fs-hint">
              This is a generator handoff, not a rendered video or a native Flow
              project file. Check the live studio’s current approval status
              before execution.
            </p>
            <textarea
              rows={15}
              aria-label="Generator-specific exported prompts"
              readOnly
              value={bundle.markdown}
              onFocus={(e) => e.target.select()}
            />
          </div>
        )}
      </div>
    </section>
  );
}
