"use client";
import type { Project, Save } from "./creative-types";
import {useEffect} from "react";
import {DraftNotice,useDraft} from "./creative-forms";
import {studioApi as api} from "./client";
export function StepDocument({project,step,busy,save,onState}: {project:Project;step:string;busy:boolean;save:Save;onState:(dirty:boolean,revision:number)=>void}) {
 const form=useDraft(project.documents[step]?.text||"",project.revision,`document:${project.id}:${step}`);
 useEffect(()=>onState(form.dirty,form.revision),[form.dirty,form.revision,onState]);
 return <div className="fs-document-editor">
   <DraftNotice conflict={form.conflict} reload={form.reload} rebase={form.rebase}/>
   <label className="fs-label" htmlFor="step-document">{step==="editor_handoff"?"Editing notes & handoff":step==="final_review"?"Final image notes":"Step document"}</label>
   <textarea id="step-document" aria-label="Step document" rows={12} value={form.draft} onChange={e=>form.edit(()=>e.target.value)} placeholder={step==="brief"?"Who is this for? What should they feel or do?":step==="script"?"Write the concept, dialogue and story beats…":step==="final_review"?"Record your final image choices, quality review and delivery notes…":"Record editing notes for your preferred editor…"}/>
   <div className="fs-document-actions"><span className="fs-hint">{form.dirty?"Unsaved draft · kept when you navigate":"Saved document"}</span><button className="fs-primary" disabled={busy||form.conflict||!form.draft.trim()} onClick={()=>save(async()=>{await api("complete_step",{project_id:project.id,expected_revision:form.revision,step,output:{text:form.draft}});form.saved();})}>Save & complete step</button></div>
 </div>;
}
