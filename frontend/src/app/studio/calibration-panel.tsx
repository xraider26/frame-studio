"use client";
import {useMemo,useState} from "react";
import {studioApi} from "./client";
import {DraftNotice,useDraft} from "./creative-forms";
import type {Project,Save} from "./creative-types";

const purposes = ["style","identity","product","layout"];

export function CalibrationPanel({project,busy,save}:{project:Project;busy:boolean;save:Save}) {
  const c=project.calibration;
  const initial=useMemo(()=>({representative_shot_id:c?.representative_shot_id||project.shots[0]?.id||"",scope:c?.scope||purposes,note:""}),[c?.representative_shot_id,c?.scope,project.shots]);
  const form=useDraft(initial,project.revision,`calibration:${project.id}`),draft=form.draft;
  const [expanded,setExpanded]=useState(false);
  const action=project.next_action;
  const rep=project.calibration_state?.representative_shot_id||c?.representative_shot_id||project.shots[0]?.id;
  const shot=project.shots.find(s=>s.id===(action.action==="await_calibration_approval"?action.shot_id:rep));
  const take=project.assets.find(a=>a.id===(action.asset_id||shot?.image_asset));
  const ready=action.action==="await_calibration_approval";
  const blocked=busy||form.conflict;
  const humanAction=(operation:string,args:Record<string,unknown>)=>save(async()=>{
    await studioApi(operation,{project_id:project.id,expected_revision:form.revision,...args});
    form.saved();
  });
  if(!c) return <section className="cv-section"><h2>Visual calibration</h2><p>This existing project keeps its review policy. You can opt in to a creator-approved visual baseline.</p><button className="fs-button" disabled={busy} onClick={()=>humanAction("set_calibration_mode",{mode:"calibration"})}>Opt in to calibration</button></section>;
  if(c.mode==="production") return <section className="cv-section"><h2>Calibration skipped by creator</h2><p>Technical inspection and workflow approval follow your saved policies.</p><button className="fs-button" disabled={busy} onClick={()=>humanAction("set_calibration_mode",{mode:"calibration"})}>Opt in to calibration</button></section>;
  return <section className="cv-section" aria-label="Visual calibration">
    <h2>Creator style acceptance</h2>
    <p>Generate one representative image, inspect it, then accept the visual baseline before continuing. Status: {project.calibration_state?.status||c.status}.</p>
    <DraftNotice {...form}/>
    <div className="fs-media-strip">{project.assets.filter(a=>a.role==="reference"&&a.kind==="image").map(a=><figure key={a.id}><img src={a.url} alt={a.name||"Calibration reference"}/><figcaption>{a.name||"Reference"}</figcaption></figure>)}{take&&<figure><img src={take.url} alt="Representative calibration take"/><figcaption>{shot?.title}</figcaption></figure>}</div>
    <h3>Technical inspection</h3>
    {take?.review?<p>Inspector: {take.review.actor} · {take.review.at}. {Object.entries(take.review.criteria).map(([key,value])=>`${key}: ${typeof value==="boolean"?(value?"pass":"fail"):value.state}`).join("; ")}</p>:<p>Awaiting actual image inspection. Record inspection evidence in Takes &amp; inspection.</p>}
    <p className="fs-hint">Technical evidence does not grant creator style acceptance. Calibration scope: {(c.scope||purposes).join(", ")}. Environment style acceptance does not approve character likeness.</p>
    <label className="fs-label">Calibration feedback<textarea aria-label="Calibration feedback" value={draft.note} onChange={e=>form.edit(v=>({...v,note:e.target.value}))}/></label>
    <div className="fs-actions">
      <button className="fs-primary" disabled={blocked||!ready||action.technical_ready===false} onClick={()=>humanAction("review_calibration",{asset_id:take?.id,approve:true,note:draft.note})}>Accept visual baseline</button>
      <button className="fs-button" disabled={blocked||!ready||!draft.note.trim()} onClick={()=>humanAction("review_calibration",{asset_id:take?.id,approve:false,note:draft.note})}>Reject and repair representative</button>
    </div>
    <details open={expanded} onToggle={e=>setExpanded(e.currentTarget.open)}><summary>Representative and calibration scope</summary>
      <label className="fs-label">Representative shot<select aria-label="Representative shot" value={draft.representative_shot_id} onChange={e=>form.edit(v=>({...v,representative_shot_id:e.target.value}))}>{project.shots.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
      <p>Choose which reference purposes this baseline covers. Narrowing fidelity is a creator decision; required production references remain recorded.</p>
      {purposes.map(p=><label key={p} className="fs-policy"><input type="checkbox" checked={draft.scope.includes(p)} onChange={e=>form.edit(v=>({...v,scope:e.target.checked?[...v.scope,p]:v.scope.filter(x=>x!==p)}))}/>{p}</label>)}
      <button className="fs-button" disabled={blocked||!draft.scope.length} onClick={()=>humanAction("configure_calibration",{representative_shot_id:draft.representative_shot_id,scope:draft.scope})}>Save calibration scope</button>
      <button className="fs-button" disabled={blocked} onClick={()=>humanAction("set_calibration_mode",{mode:"production"})}>Skip calibration</button>
    </details>
    {c.history.some(h=>h.decision==="reject")&&<details open><summary>Rejected attempts preserved</summary>{c.history.filter(h=>h.decision==="reject").map((h,i)=>{const a=project.assets.find(a=>a.id===h.asset_id);return <figure key={i}>{a&&<img src={a.url} alt="Rejected calibration attempt" style={{maxWidth:240}}/>}<figcaption>{h.actor} · {h.at}: {h.note}</figcaption></figure>;})}</details>}
    {c.history.filter(h=>h.decision==="approve").map((h,i)=><p className="fs-hint" key={i}>Creator acceptance: {h.actor} · {h.at} · scope {(h.scope||[]).join(", ")} · {h.note}</p>)}
  </section>;
}
