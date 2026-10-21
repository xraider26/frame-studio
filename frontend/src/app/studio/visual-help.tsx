"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HelpCircle, X } from "lucide-react";
import type { Technique } from "./creative-types";

/** Consistent illustrative scene: visual intent, never a certified camera simulation. */
export function TechniqueVisual({
  kind,
  variant,
}: {
  kind: string;
  variant: string;
}) {
  const id = useId().replaceAll(":", "");
  const lighting = kind === "lighting";
  const close = ["close", "extreme", "telephoto"].includes(variant);
  const wide = ["wide", "environment"].includes(variant);
  const low = ["low", "hard", "rembrandt"].includes(variant);
  const tint =
    variant === "blue"
      ? "#587caa"
      : variant === "neon"
        ? "#527e89"
        : variant === "noir"
          ? "#777"
          : "#a77950";
  const scale = close ? 1.65 : wide ? 0.75 : 1;
  return (
    <figure className={`cv-illustration cv-${kind} cv-${variant}`}>
      <svg
        viewBox="0 0 360 190"
        role="img"
        aria-label={`${kind} illustration: ${variant}`}
      >
        <defs>
          <linearGradient id={`sky${id}`} x2="0" y2="1">
            <stop stopColor={low ? "#141923" : tint} />
            <stop offset="1" stopColor="#24262a" />
          </linearGradient>
          <radialGradient
            id={`face${id}`}
            cx={variant === "rim" ? "80%" : "25%"}
          >
            <stop stopColor={variant === "golden" ? "#ffe0a2" : "#e8c2a2"} />
            <stop offset="1" stopColor={low ? "#352b2b" : "#9b7262"} />
          </radialGradient>
          <filter id={`soft${id}`}>
            <feGaussianBlur stdDeviation="3" />
          </filter>
          <pattern
            id={`grain${id}`}
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="2" cy="1" r=".6" fill="#fff" opacity=".22" />
            <circle cx="5" cy="5" r=".7" fill="#000" opacity=".3" />
          </pattern>
        </defs>
        <rect width="360" height="190" fill={`url(#sky${id})`} />
        <g filter={close ? `url(#soft${id})` : undefined}>
          <path
            d="M0 134 L55 75 L112 120 L170 65 L236 130 L310 87 L360 130 V190 H0"
            fill="#172024"
          />
          <path
            d="M18 30H83V126H18Z"
            fill={variant === "practical" ? "#edac54" : "#a5b7b2"}
            opacity={low ? 0.14 : 0.28}
          />
          <path d="M50 30V126M18 78H83" stroke="#21272c" strokeWidth="4" />
          <rect x="285" y="40" width="3" height="120" fill="#473f3a" />
          <path
            d="M266 42h41l-9-15h-23Z"
            fill="#f4c38b"
            opacity={variant === "practical" ? 1 : 0.3}
          />
        </g>
        <path d="M0 155L360 141V190H0" fill="#393b39" />
        <g
          transform={`translate(180 155) scale(${scale}) translate(-180 -155)`}
        >
          <ellipse
            cx="182"
            cy="172"
            rx="43"
            ry="7"
            fill="#080c10"
            opacity=".4"
          />
          <path
            d="M153 170l5-64q23-22 47 0l8 64"
            fill={variant === "noir" ? "#555" : "#9b533a"}
            stroke={variant === "2d" ? "#15191e" : "none"}
            strokeWidth="3"
          />
          <path d="M173 111l2-20h15l2 20" fill="#b38570" />
          <ellipse cx="182" cy="73" rx="22" ry="29" fill={`url(#face${id})`} />
          <path
            d="M160 73q-5-37 23-34q28 2 22 34l-11-22q-22 8-34 22"
            fill="#302a2b"
          />
          <path d="M169 74h8m11 0h8" stroke="#2b2a2a" strokeWidth="2" />
          <path
            d="M177 91q6 4 12-1"
            fill="none"
            stroke="#744f46"
            strokeWidth="2"
          />
          {variant === "rim" && (
            <path
              d="M204 65q9 33-8 40l16 65"
              fill="none"
              stroke="#ffdc9e"
              strokeWidth="3"
            />
          )}
        </g>
        {variant === "anamorphic" && (
          <path d="M210 56H350" stroke="#91c7d9" strokeWidth="2" opacity=".6" />
        )}
        {["film", "clay", "watercolour"].includes(variant) && (
          <rect width="360" height="190" fill={`url(#grain${id})`} />
        )}
        {kind === "movement" && (
          <g
            className={`cv-motion cv-motion-${variant}`}
            fill="none"
            stroke="#ffc28c"
            strokeWidth="2"
          >
            <path
              d={
                variant === "orbit"
                  ? "M118 159Q180 199 240 154"
                  : variant === "dolly"
                    ? "M167 162V126m-6 8 6-8 6 8"
                    : variant === "tilt"
                      ? "M235 123V65m-6 8 6-8 6 8"
                      : variant === "locked"
                        ? "M156 138h48v25h-48Z"
                        : "M105 148H257m-9-6 9 6-9 6"
              }
            />
          </g>
        )}
        {lighting && (
          <g fill="none" stroke="#ffca90" opacity=".65">
            <path
              d={
                variant === "rim"
                  ? "M284 50L195 72"
                  : variant === "high"
                    ? "M72 45L182 85"
                    : "M50 60L166 80"
              }
              strokeDasharray="5 4"
            />
            <circle
              cx={variant === "rim" ? 284 : 50}
              cy={variant === "rim" ? 50 : 60}
              r="9"
            />
          </g>
        )}
        <path
          d="M12 28V12H29M331 12H348V28M12 162V178H29M331 178H348V162"
          stroke="#dfd7cf"
          fill="none"
          opacity=".4"
        />
      </svg>
      <figcaption>
        Illustrative {kind === "camera" ? "look" : kind} · same reference scene
        · not a generator prediction
      </figcaption>
    </figure>
  );
}

export function VisualHelp({
  label,
  category,
  value = "",
  entries = [],
  onApply,
}: {
  label: string;
  category: string;
  value?: string;
  entries?: Technique[];
  onApply?: (entry: Technique) => void;
}) {
  const [open, setOpen] = useState(false),
    [pinned, setPinned] = useState(false),
    [chosen, setChosen] = useState("");
  const trigger = useRef<HTMLButtonElement>(null),
    panel = useRef<HTMLDivElement>(null);
  const grace = useRef<ReturnType<typeof setTimeout> | null>(null),
    suppressFocus = useRef(false);
  const [pos, setPos] = useState({ left: 12, top: 12 });
  const id = useId();
  const options = entries.filter((e) => e.category === category);
  const entry =
    options.find((e) => e.id === chosen) ||
    options.find(
      (e) =>
        JSON.stringify(e.apply).toLowerCase().includes(value.toLowerCase()) &&
        value,
    ) ||
    options[0];
  const cancelGrace = useCallback(() => {
    if (grace.current) clearTimeout(grace.current);
  }, []);
  const dismiss = useCallback(() => {
    cancelGrace();
    setOpen(false);
    setPinned(false);
    setChosen("");
  }, [cancelGrace]);
  function leave() {
    cancelGrace();
    if (!pinned) grace.current = setTimeout(() => setOpen(false), 180);
  }
  const restoreFocus = useCallback(() => {
    suppressFocus.current = window.document.activeElement !== trigger.current;
    dismiss();
    trigger.current?.focus();
  }, [dismiss]);
  function show() {
    cancelGrace();
    if (trigger.current) {
      const r = trigger.current.getBoundingClientRect();
      setPos({
        left: Math.max(
          12,
          Math.min(
            r.left,
            window.innerWidth - Math.min(390, window.innerWidth - 24) - 12,
          ),
        ),
        top: Math.max(12, Math.min(r.bottom + 8, window.innerHeight - 560)),
      });
    }
    setOpen(true);
  }
  useEffect(() => () => cancelGrace(), [cancelGrace]);
  useEffect(() => {
    if (!open) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") restoreFocus();
    };
    const outside = (e: PointerEvent) => {
      if (
        !panel.current?.contains(e.target as Node) &&
        !trigger.current?.contains(e.target as Node)
      )
        dismiss();
    };
    window.addEventListener("keydown", close);
    window.addEventListener("pointerdown", outside);
    return () => {
      window.removeEventListener("keydown", close);
      window.removeEventListener("pointerdown", outside);
    };
  }, [open, dismiss, restoreFocus]);
  const exact = options.some(
    (e) =>
      JSON.stringify(e.apply).toLowerCase().includes(value.toLowerCase()) &&
      value,
  );
  const content = (
    <div
      ref={panel}
      id={id}
      role="dialog"
      aria-label={`${label} guide`}
      className="cv-help-panel"
      style={pos}
      onMouseEnter={show}
      onMouseLeave={leave}
      onFocus={cancelGrace}
      onBlur={(e) => {
        if (
          !pinned &&
          !e.currentTarget.contains(e.relatedTarget) &&
          e.relatedTarget !== trigger.current
        )
          leave();
      }}
    >
      <div className="cv-help-heading">
        <span>{label}</span>
        <button
          type="button"
          aria-label="Close option help"
          onClick={restoreFocus}
        >
          <X size={17} />
        </button>
      </div>
      <TechniqueVisual
        kind={category}
        variant={entry?.visual.variant || category}
      />
      {value && !exact && !chosen && (
        <small>
          Custom direction: {value}. The illustration below is a category
          example, not a prediction of this custom value.
        </small>
      )}
      {options.length > 0 && (
        <label className="cv-help-example">
          Explore an example
          <select
            aria-label={`${label} example`}
            value={entry?.id || ""}
            onChange={(e) => setChosen(e.target.value)}
          >
            {options.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <p>
        {entry?.explanation ||
          `Describe the ${label.toLowerCase()} you intend. Blank values inherit the project direction; custom values remain editable.`}
      </p>
      {entry && (
        <>
          <div className="cv-help-note">
            <strong>Use it for</strong>
            <p>{entry.use_when}</p>
            <strong>Watch for</strong>
            <p>{entry.risk}</p>
          </div>
          <small>{entry.source_note}</small>
          {onApply && (
            <button
              className="fs-primary"
              type="button"
              onClick={() => {
                onApply(entry);
                dismiss();
              }}
            >
              Use this technique
            </button>
          )}
        </>
      )}
    </div>
  );
  return (
    <span className="cv-help-anchor" onMouseLeave={leave}>
      <button
        ref={trigger}
        type="button"
        className="cv-help-button"
        aria-label={`Help: ${label}`}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-haspopup="dialog"
        onMouseEnter={show}
        onFocus={() => {
          if (suppressFocus.current) {
            suppressFocus.current = false;
            return;
          }
          show();
        }}
        onBlur={(e) => {
          if (!panel.current?.contains(e.relatedTarget)) leave();
        }}
        onClick={() => {
          if (pinned) dismiss();
          else {
            show();
            setPinned(true);
          }
        }}
      >
        <HelpCircle size={14} />
      </button>
      {open && createPortal(content, window.document.body)}
    </span>
  );
}
