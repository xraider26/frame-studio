"use client";
import { useEffect, useMemo, useState } from "react";
import { studioApi as api } from "./client";
import type { Project, Save } from "./creative-types";
import { useDraft, DraftNotice } from "./creative-forms";

type Trial = {id:string;idea:string;note:string;defects:string;passed:boolean;at:string;matches_current_inputs:boolean;model_scope:{capabilities:{model:string}};final_file:{sha256:string};attempts:number};
type Report = {revision:number;final_checks:string[];scope:string;trials:Trial[]};
export function RecipeTrials({project,busy,save}:{project:Project;busy:boolean;save:Save}){
  const [report,setReport]=useState<Report|null>(null);
  const [error,setError]=useState("");
  const initial=useMemo(()=>({idea:"",note:"",defects:"",watched:false,criteria:{} as Record<string,boolean>}),[]);
  const form=useDraft(initial,project.revision,"recipe-trial:"+project.id);
  const {idea,note,defects,watched,criteria}=form.draft;
  const [reload,setReload]=useState(0);
  useEffect(()=>{let active=true;api<Report>("recipe_trials",{project_id:project.id}).then(v=>{if(active){setReport(v);setError("");}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[project.id,project.revision,reload]);
  const finalId=project.documents?.final_review?.export_asset_id;
  const final=project.assets.find(a=>a.id===finalId && a.kind==="final_video" && !a.stale);
  return <section className="cv-recipe-trials" aria-label="Finished production assessment">
    <h3>Recorded video trials</h3>
    {error && <p role="alert">{error} <button className="fs-link" onClick={()=>setReload(n=>n+1)}>Retry trials</button></p>}
    {report && <>
      <p className="fs-hint">{report.scope}</p>
      {!report.trials.length && <p>No reviewed final productions recorded.</p>}
      {report.trials.map(t=><article className="cv-source-rule" key={t.id}><small>{t.passed?"HUMAN-REVIEWED PASS":"NEEDS REVISION"} · {t.matches_current_inputs?"MATCHES CURRENT INPUTS":"HISTORICAL INPUTS"}</small><h3>{t.idea}</h3><p>{t.note}</p>{t.defects && <p>{t.defects}</p>}<p className="fs-hint">{t.model_scope.capabilities.model} · {t.at} · {t.attempts} attempts · file {t.final_file.sha256.slice(0,12)}</p></article>)}
      {!final ? <p className="fs-hint">Import the actual final edit through the editing workflow before recording a trial. Selected clips and illustrative stills do not qualify.</p> : <details><summary>Record a final-production assessment</summary>
        <p className="fs-hint">Watch the complete export. Record pass or fail for every criterion; this does not change your workflow approvals.</p>
        <DraftNotice {...form}/>
        <label className="fs-label">Idea tested<input value={idea} onChange={e=>form.edit(v=>({...v,idea:e.target.value}))} maxLength={1000}/></label>
        <label className="fs-label">Human observations<textarea value={note} onChange={e=>form.edit(v=>({...v,note:e.target.value}))} maxLength={8000}/></label>
        <label className="cv-trial-watch"><input type="checkbox" checked={watched} onChange={e=>form.edit(v=>({...v,watched:e.target.checked}))}/> I watched the full final edit and inspected its beginning, middle and end.</label>
        {report.final_checks.map(c=><fieldset className="cv-trial-check" key={c}><legend>{c}</legend>{[true,false].map(v=><label key={String(v)}><input type="radio" name={c} checked={criteria[c]===v} onChange={()=>form.edit(old=>({...old,criteria:{...old.criteria,[c]:v}}))}/>{v?"Pass":"Fail"}</label>)}</fieldset>)}
        <label className="fs-label">Remaining defects<textarea value={defects} onChange={e=>form.edit(v=>({...v,defects:e.target.value}))} maxLength={8000}/></label>
        <button className="fs-primary" disabled={busy || form.conflict || !watched || !idea.trim() || !note.trim() || report.final_checks.some(c=>typeof criteria[c]!=="boolean")} onClick={()=>save(async()=>{
          await api("record_recipe_trial",{project_id:project.id,expected_revision:form.revision,assessment:{asset_id:final.id,idea,note,defects,criteria:Object.fromEntries(report.final_checks.map(c=>[c,criteria[c]])),watched_full:watched,inspected:["beginning","middle","end"]}});
          form.reload();
          setReload(n=>n+1);
        })}>Record human assessment</button>
      </details>}
    </>}
  </section>;
}
