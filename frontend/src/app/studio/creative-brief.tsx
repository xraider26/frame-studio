"use client";
import { useMemo } from "react";
import { DraftNotice, useDraft } from "./creative-forms";
import { studioApi } from "./client";
import type { Project, Save } from "./creative-types";
export const briefFields = [
  ["vision", "What should the finished work show or communicate?"],
  ["art_style", "What art style or visual direction do you want?"],
  ["purpose", "What will this work be used for?"],
  ["audience", "Who is it for? (optional)"],
  ["constraints", "Any must-haves or limits? (optional)"],
];
export function BriefFields({
  answers,
  onChange,
}: {
  answers: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
}) {
  return (
    <div className="fs-form-grid">
      {briefFields.map(([id, prompt]) => (
        <label className="fs-label" key={id}>
          {prompt}
          <textarea
            rows={2}
            value={answers[id] || ""}
            onChange={(e) => onChange({ ...answers, [id]: e.target.value })}
          />
        </label>
      ))}
    </div>
  );
}
export function CreativeBrief({
  project,
  busy,
  save,
}: {
  project: Project;
  busy: boolean;
  save: Save;
}) {
  const source = useMemo(
    () => ({
      ...project.settings.creative_intake,
      ...project.creative_intake?.answers,
    }),
    [project.settings.creative_intake, project.creative_intake?.answers],
  );
  const form = useDraft<Record<string, string>>(
    source,
    project.revision,
    "creative-brief:" + project.id,
  );
  const answers = form.draft;
  const setAnswers = (value: Record<string, string>) => form.edit(() => value);
  const questions =
    project.creative_intake?.questions ||
    briefFields
      .slice(0, 3)
      .filter(([id]) => !answers[id]?.trim())
      .map(([id, prompt]) => ({ id, prompt }));
  return (
    <section
      className="cv-section cv-creative-brief"
      aria-label="Creative brief"
    >
      <div className="fs-eyebrow">CREATIVE BRIEF</div>
      <h2>
        {questions.length
          ? "Tell your agent what matters."
          : "Your creative direction"}
      </h2>
      {questions.length > 0 && (
        <div role="status">
          <p>Your agent needs these details before making creative choices:</p>
          <ul>
            {questions.map((q) => (
              <li key={q.id}>{q.prompt}</li>
            ))}
          </ul>
        </div>
      )}
      <DraftNotice {...form} />
      <BriefFields answers={answers} onChange={setAnswers} />
      <button
        className="fs-primary"
        disabled={busy || form.conflict}
        onClick={() =>
          save(async () => {
            await studioApi("update_settings", {
              project_id: project.id,
              expected_revision: form.revision,
              settings: { creative_intake: answers },
            });
            form.saved();
          })
        }
      >
        Save creative brief
      </button>
      <p className="fs-hint">
        Generator, model and technical suggestions remain editable in Generator
        handoff and Production settings.
      </p>
    </section>
  );
}
