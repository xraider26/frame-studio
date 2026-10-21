"use client";
import { Field } from "./creative-forms";
import { mergeRecord, type Direction, type Catalog } from "./creative-types";

export function ProjectDirection({
  value,
  onChange,
  catalog,
}: {
  value: Direction;
  onChange: (d: Direction) => void;
  catalog: Catalog | null;
}) {
  const groups: {
    group: "camera" | "lighting" | "art";
    fields: [string, string, string][];
  }[] = [
    {
      group: "camera",
      fields: [
        ["body_look", "Camera look", "camera"],
        ["lens", "Lens feel", "lens"],
        ["aperture", "Aperture / depth cue", "lens"],
        ["framing", "Shot size", "framing"],
        ["angle", "Angle", "framing"],
        ["move", "Camera movement", "movement"],
        ["speed", "Movement speed", "movement"],
      ],
    },
    {
      group: "lighting",
      fields: [
        ["technique", "Lighting technique", "lighting"],
        ["world_source", "Physical light source", "lighting"],
        ["direction", "Camera-relative light direction", "lighting"],
        ["softness", "Source softness", "lighting"],
        ["contrast", "Contrast / shadow depth", "lighting"],
        ["temperature", "Colour temperature / tint", "lighting"],
        ["practicals", "Visible practicals", "lighting"],
      ],
    },
    {
      group: "art",
      fields: [
        ["style", "Visual treatment", "style"],
        ["palette", "Colour palette", "palette"],
        ["materials", "Material rules", "style"],
        ["texture", "Texture", "style"],
      ],
    },
  ];
  return (
    <details className="cv-project-defaults">
      <summary>Project-wide advanced direction</summary>
      <p className="fs-body">
        Set a common visual language here. A shot override replaces it. Blank
        values inherit the basic project settings.
      </p>
      {groups.map(({ group, fields }) => (
        <div className="cv-section" key={group}>
          <h3>{group[0].toUpperCase() + group.slice(1)}</h3>
          <div className="cv-form-grid">
            {fields.map(([key, label, help]) => (
              <Field
                key={key}
                label={`Project ${label.toLowerCase()}`}
                value={value[group][key] || ""}
                onChange={(v) =>
                  onChange(mergeRecord(value, { [group]: { [key]: v } }))
                }
                help={help}
                entries={catalog?.entries}
                options={[
                  ...new Set(
                    (catalog?.entries || []).flatMap((e) =>
                      e.apply[group]?.[key] ? [e.apply[group]![key]] : [],
                    ),
                  ),
                ]}
                onApply={(entry) => onChange(mergeRecord(value, entry.apply))}
              />
            ))}
          </div>
        </div>
      ))}
      <div className="cv-form-grid">
        {[
          ["voice", "Voice direction"],
          ["ambience", "Ambience"],
          ["foley", "Foley direction"],
          ["music", "Music intent"],
        ].map(([key, label]) => (
          <Field
            key={key}
            label={`Project ${label.toLowerCase()}`}
            value={String(value.sound[key as keyof typeof value.sound] || "")}
            onChange={(v) =>
              onChange(
                mergeRecord(value, { sound: { ...value.sound, [key]: v } }),
              )
            }
            help="sound"
            entries={catalog?.entries}
          />
        ))}
      </div>
      <p className="fs-hint">
        These are unapplied defaults until you save Production settings below.
      </p>
    </details>
  );
}
