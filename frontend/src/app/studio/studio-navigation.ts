import type { Action } from "./creative-types";
export type Stage = "brief" | "plan" | "create" | "review" | "export";
export type NavigationTarget = { view: string; step?: string };
export function stageForView(view: string, step?: string): Stage | null {
  if (view === "home") return "brief";
  if (["story", "bible", "shots", "knowledge", "sequences"].includes(view)) return "plan";
  if (["generator", "import"].includes(view)) return "create";
  if (["review", "takes"].includes(view)) return "review";
  if (["handoff", "delivery"].includes(view)) return "export";
  if (view === "workflow") {
    if (step === "brief") return "brief";
    if (step === "script") return "plan";
    if (step === "editor_handoff") return "export";
    return "review";
  }
  return null;
}
export function nextActionTarget(action: Action | undefined, outputType: "image" | "video" = "video"): NavigationTarget {
  if (!action || action.action === "ask_creator") return {view:"home"};
  switch(action.action) {
    case "generate": return {view:"generator"};
    case "write_prompt":
    case "prepare_shots": return {view:"shots"};
    case "quality_attention":
    case "record_quality": return {view:"takes"};
    case "await_approval": return {view:"review",step:action.step};
    case "resolve_resources": return {view:"production"};
    case "resolve_preflight": return {view:"shots"};
    case "complete": return {view:outputType === "image" ? "delivery" : "handoff"};
    case "prepare_step":
      return ["visual_direction", "pilot", "production"].includes(action.step) ? {view:"shots"} : {view:"workflow",step:action.step};
    default: return {view:"workflow",step:action.step || "brief"};
  }
}
export function templatesForOutput<T extends {id:string;output_type?:"image"|"video"}>(templates: T[], kind:"image"|"video"):T[] {
  return templates.filter(t => (t.output_type || "video") === kind);
}
export function templateForOutput<T extends {id:string;output_type?:"image"|"video"}>(templates:T[], kind:"image"|"video", current:string):string {
  const choices = templatesForOutput(templates,kind);
  return choices.find(t=>t.id===current)?.id || choices.find(t=>t.id===(kind === "image" ? "image-custom" : "ai-film"))?.id || choices[0]?.id || "";
}

export const projectStages: {id:Stage;label:string;view:string}[] = [
  {id:"brief",label:"Brief",view:"home"},
  {id:"plan",label:"Plan",view:"story"},
  {id:"create",label:"Create",view:"generator"},
  {id:"review",label:"Review",view:"takes"},
  {id:"export",label:"Export",view:"handoff"},
];
export function stageTabs(stage: Stage, imageOnly: boolean): (NavigationTarget & {label:string})[] {
  switch(stage) {
    case "brief": return [{view:"home",label:"Creative brief"},{view:"workflow",step:"brief",label:"Brief document"}];
    case "plan": return [{view:"story",label:imageOnly?"Visual concept":"Story & timing"},{view:"workflow",step:"script",label:imageOnly?"Concept document":"Script document"},{view:"bible",label:"Production bible"},{view:"shots",label:"Shots & direction"},...(!imageOnly?[{view:"sequences",label:"Sequences"}]:[]),{view:"knowledge",label:"Visual library"}];
    case "create": return [{view:"generator",label:"Generator handoff"},{view:"import",label:"Return output & import"}];
    case "review": return [{view:"takes",label:"Takes & quality"},{view:"review",label:"Approvals"},{view:"workflow",step:"final_review",label:imageOnly?"Final image check":"Final check"}];
    case "export": return imageOnly?[{view:"delivery",label:"Image handoff"}]:[{view:"handoff",label:"Editor handoff"},{view:"workflow",step:"editor_handoff",label:"Handoff notes"}];
  }
}
