"use client";
import { useId, useState } from "react";
import { RecipeWorkspace } from "./recipe-workspace";
import {
  TemplateWorkspace,
  type SavedTemplate,
  type TemplateChoice,
} from "./template-workspace";
import type { Project, Save } from "./creative-types";

function ChoiceTabs({
  label,
  values,
  value,
  onChange,
}: {
  label: string;
  values: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="os-library-tabs" role="tablist" aria-label={label}>
      {values.map((name, index) => (
        <button
          key={name}
          role="tab"
          id={`${id}-${index}`}
          aria-selected={value === name}
          tabIndex={value === name ? 0 : -1}
          onClick={() => onChange(name)}
          onKeyDown={(event) => {
            let next = index;
            if (event.key === "ArrowRight") next = (index + 1) % values.length;
            else if (event.key === "ArrowLeft")
              next = (index + values.length - 1) % values.length;
            else if (event.key === "Home") next = 0;
            else if (event.key === "End") next = values.length - 1;
            else return;
            event.preventDefault();
            onChange(values[next]);
            document.getElementById(`${id}-${next}`)?.focus();
          }}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

export function TemplateHub({
  project,
  choices,
  busy,
  save,
  onNew,
}: {
  project: Project | null;
  choices: TemplateChoice[];
  busy: boolean;
  save: Save;
  onNew: (id: string, outputType?: "image" | "video") => void;
}) {
  const [kind, setKind] = useState<"Image" | "Video">(
    project?.output_type === "image" ? "Image" : "Video",
  );
  const [source, setSource] = useState("Built-in");
  const outputType = kind === "Image" ? "image" : "video";
  const matchingProject =
    project && (project.output_type || "video") === outputType ? project : null;
  const saved = choices.filter(
    (t) => t.saved && (t.output_type || "video") === outputType,
  ) as SavedTemplate[];
  return (
    <section className="os-template-hub" aria-label="Template library">
      <div className="os-library-heading">
        <div>
          <div className="fs-eyebrow">STARTING POINTS</div>
          <h2>Templates</h2>
          <p className="fs-body">
            Choose the output, then a format. Every setup stays editable.
          </p>
        </div>
        {project && (
          <button
            className="fs-button"
            onClick={() => {
              setKind(project.output_type === "image" ? "Image" : "Video");
              setSource("Saved");
            }}
          >
            Save current setup
          </button>
        )}
      </div>
      <div className="os-library-filters">
        <ChoiceTabs
          label="Template media"
          values={["Video", "Image"]}
          value={kind}
          onChange={(value) => setKind(value as "Video" | "Image")}
        />
        <ChoiceTabs
          label="Template source"
          values={["Built-in", "Saved"]}
          value={source}
          onChange={setSource}
        />
      </div>
      <div className="os-library-content" aria-live="polite">
        {source === "Built-in" ? (
          <RecipeWorkspace
            key={outputType}
            project={matchingProject}
            outputType={outputType}
            busy={busy}
            save={save}
            onNew={(id) => onNew(id, outputType)}
          />
        ) : (
          <TemplateWorkspace
            key={outputType}
            project={matchingProject}
            templates={saved}
            busy={busy}
            save={save}
            onNew={(id) => onNew(id, outputType)}
          />
        )}
      </div>
    </section>
  );
}
