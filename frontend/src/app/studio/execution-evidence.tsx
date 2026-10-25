"use client";
import {useEffect, useState} from "react";
import {studioApi} from "./client";
import type { Job, Asset } from "./creative-types";

type Rule = {
  rule_id: string; required: boolean; phase: string; status: string; reason?: string; outcome?: string;
  provenance?: string; source_id?: string; source_locator?: string; rule_version?: number;
  original_page_citations?: unknown[]; studio_correction?: unknown;
  predicate_result?: { applicable?: boolean; reason?: string; scope?: unknown[] }; bindings?: unknown[];
};
const pretty = (value: unknown) => JSON.stringify(value, null, 2);

export function ExecutionEvidence({ job, asset }: { job?: Job; asset?: Pick<Asset, "kind" | "review"> }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<Job>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open || !job) return;
    let current = true;
    studioApi<Job>("get_job", {job_id: job.id, detail: "full"})
      .then(value => {if (current) {setDetail(value); setError("");}})
      .catch(e => {if (current) setError(e.message);});
    return () => {current = false;};
  }, [open, job?.id, job?.execution?.request_hash]);
  const selected = detail?.id === job?.id ? detail : job;
  const handoff = selected?.handoff || {}, execution = selected?.execution;
  const rules = (handoff.rule_application || []) as Rule[];
  return <details className="cv-section" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Execution evidence · {execution?.validation.state || "unavailable"}</summary>
    {error && <p role="alert">{error}</p>}
    <p>Rule mappings establish traceability. Actual media inspection and creator acceptance are separate decisions.</p>
    <p>Evidence source: <strong>{execution?.evidence_source || "unavailable"}</strong>{execution && <> · {execution.tool} · request {execution.request_hash}</>}</p>
    <p>Prompt comparison: {execution?.validation.prompt_match || "unavailable"}. Reference comparison: {execution?.validation.references_match || "unavailable"}. Only line endings normalize automatically.</p>
    <h3>Compiled positive prompt</h3><pre style={{whiteSpace:"pre-wrap"}}>{String(handoff.prompt || "unavailable")}</pre>
    <h3>Compiled negative prompt</h3><pre style={{whiteSpace:"pre-wrap"}}>{String(handoff.negative_prompt ?? "unavailable")}</pre>
    <h3>Actual submitted positive prompt</h3><pre style={{whiteSpace:"pre-wrap"}}>{execution?.prompt ?? "unavailable"}</pre>
    <h3>Actual submitted negative prompt</h3><pre style={{whiteSpace:"pre-wrap"}}>{execution?.negative_prompt ?? "unavailable"}</pre>
    {execution?.validation.state === "mismatch" && <p role="status">The submitted content differs from the compiled request. Revise the saved inputs and create a new claim; retain this take for review.</p>}
    <h3>Compiled references and versions</h3><pre>{pretty(handoff.references || [])}</pre>
    <h3>Actual references and supplied arguments</h3><pre style={{whiteSpace:"pre-wrap"}}>{execution ? pretty({references:execution.references, arguments:execution.arguments, unsupported_constraints:execution.unsupported_constraints}) : "unavailable"}</pre>
    <h3>Unresolved execution constraints</h3><pre style={{whiteSpace:"pre-wrap"}}>{pretty(handoff.execution_contract || "unavailable")}</pre>
    <h3>Actual media inspection</h3>
    <pre style={{whiteSpace:"pre-wrap"}}>{asset?.review ? pretty(asset.review) : "pending actual inspection"}</pre>
    <h3>Applicable source rules and scope</h3>
    {!rules.length && <p>Rule evidence unavailable for this legacy or imported take.</p>}
    {rules.map((r,i)=>{
      const checks = (r.bindings || []) as {criterion?: string}[];
      const review = asset?.review;
      const inspected = !!review && (asset?.kind === "image" ? review.inspected.includes("image") : ["beginning","middle","end"].every(segment=>review.inspected.includes(segment)));
      const states = checks.filter(b=>b.criterion).map(b=>review?.criteria[b.criterion!]);
      const passed = (value: unknown) => value === true || (typeof value === "object" && value !== null && "state" in value && value.state === "pass");
      const failed = (value: unknown) => value === false || (typeof value === "object" && value !== null && "state" in value && value.state === "fail");
      const outcome = r.phase === "media_review" && r.status !== "not_applicable" && review
        ? review.defect || states.some(failed) ? "failed"
          : inspected && states.length && states.every(passed) ? "inspected" : "unverified"
        : r.outcome;
      return <article key={`${r.rule_id}-${i}`}>
      <strong>{r.rule_id} · {r.required ? "required" : "guidance"} · {r.status}</strong>
      <p>{r.phase}{outcome ? ` · outcome ${outcome}` : ""} · {r.reason}</p>
      <p>{r.predicate_result?.reason}</p>
      <pre style={{whiteSpace:"pre-wrap"}}>{pretty({source:r.source_id,version:r.rule_version,locator:r.source_locator,provenance:r.provenance,original_page_citations:r.original_page_citations,studio_correction:r.studio_correction,scope:r.predicate_result?.scope,bindings:r.bindings})}</pre>
    </article>;})}
  </details>;
}
