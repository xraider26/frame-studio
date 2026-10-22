"use client";
import { useId, useSyncExternalStore, type ReactNode } from "react";

export type ControlMode = "basic" | "professional";
type Workspace = "directing" | "production" | "generator" | "queue" | "recipe";
const localModes = new Map<Workspace, ControlMode>();
const memoryOnly = new Set<Workspace>();
const eventName = "frame-control-mode-change";

function subscribe(listener: () => void) {
  window.addEventListener("storage", listener);
  window.addEventListener(eventName, listener);
  return () => {
    window.removeEventListener("storage", listener);
    window.removeEventListener(eventName, listener);
  };
}

/** UI preferences never touch a saved project or its independent form draft. */
export function useControlMode(workspace: Workspace) {
  const mode = useSyncExternalStore(
    subscribe,
    () => {
      if (memoryOnly.has(workspace)) return localModes.get(workspace) || "basic";
      try {
        return window.localStorage.getItem(`frame-control-mode:${workspace}`) ===
          "professional"
          ? "professional"
          : "basic";
      } catch {
        return localModes.get(workspace) || "basic";
      }
    },
    () => "basic",
  ) as ControlMode;
  function setMode(next: ControlMode) {
    localModes.set(workspace, next);
    try {
      window.localStorage.setItem(`frame-control-mode:${workspace}`, next);
      memoryOnly.delete(workspace);
    } catch {
      // Full/disabled storage must not prevent switching the current UI.
      memoryOnly.add(workspace);
    }
    window.dispatchEvent(new window.Event(eventName));
  }
  return [mode, setMode] as const;
}

export function ControlModeSwitch({
  mode,
  onChange,
  label,
}: {
  mode: ControlMode;
  onChange: (mode: ControlMode) => void;
  label: string;
}) {
  const hint = useId();
  return (
    <div className="cv-control-mode">
      <div
        role="radiogroup"
        aria-label={`${label} controls`}
        aria-describedby={hint}
      >
        {(["basic", "professional"] as const).map((value, i) => (
          <button
            type="button"
            role="radio"
            aria-checked={mode === value}
            tabIndex={mode === value ? 0 : -1}
            key={value}
            onClick={() => onChange(value)}
            onKeyDown={(event) => {
              const key = event.key;
              if (![
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End",
              ].includes(key)) return;
              event.preventDefault();
              const nextIndex = key === "Home" ? 0 : key === "End" ? 1 : 1 - i;
              onChange(nextIndex === 0 ? "basic" : "professional");
              event.currentTarget.parentElement
                ?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[nextIndex]
                ?.focus();
            }}
          >
            {value === "basic" ? "Basic" : "Professional"}
          </button>
        ))}
      </div>
      <p id={hint}>
        {mode === "basic"
          ? "Essential controls. Professional shows all optional detail."
          : "All controls available."}{" "}
        Your values stay unchanged when switching.
      </p>
    </div>
  );
}

/** Keep children mounted so switching cannot reset local editor state. */
export function ModeDetail({
  mode,
  advanced = true,
  children,
}: {
  mode: ControlMode;
  advanced?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="cv-mode-detail" hidden={advanced && mode === "basic"}>
      {children}
    </div>
  );
}
