"use client";
import {useId,useMemo,useState} from "react";
import {DraftNotice,useDraft} from "./creative-forms";
import {studioApi} from "./client";
import type {GenerationSetup, GeneratorSelection, Project} from "./creative-types";
import {serializeGenerationSetup} from "./generator-settings";

type Profile = {id:string;name:string};
type FieldsProps = {outputType:string;value:GenerationSetup;onChange:(value:GenerationSetup)=>void;imageProfiles?:Profile[];videoProfiles?:Profile[]};

export function GeneratorSetupFields({outputType,value,onChange,imageProfiles=[],videoProfiles=[]}:FieldsProps) {
  function change(kind:"image"|"video",patch:Partial<GeneratorSelection>) {
    onChange({...value,[kind]:{executor:"external_handoff",tool_name:"",profile:kind==="image"?"general_image":"flow_veo",model:null,model_version_status:"unknown",connection_id:null,selection_source:"creator_statement",source_text:"",...value[kind],...patch}});
  }
  return <fieldset className="fs-form-grid"><legend data-generator-question>Which generators will you use for {outputType==="image"?"images":"images and videos"}?</legend>
    <p className="fs-hint">You can use this AI&apos;s built-in image tool, another app, or a connected service. We remember this per project. Managed model versions can stay unknown.</p>
    {(["image",...(outputType==="image"?[]:["video"])] as ("image"|"video")[]).map(kind=>{
      const title=kind==="image"?"Image":"Video",item=value[kind],profiles=kind==="image"?imageProfiles:videoProfiles;
      return <div key={kind}>
        <label className="fs-label">{title} executor<select aria-label={`${title} executor`} value={item?.executor||(kind in value?"deferred":"")} onChange={e=>{
          const executor=e.target.value;
          if(executor==="deferred") onChange({...value,[kind]:null});
          else if(executor) change(kind,{executor:executor as GeneratorSelection["executor"],tool_name:executor==="agent_builtin"?"Built-in image tool":"",model:null,model_version_status:executor==="agent_builtin"?"managed":"unknown",connection_id:null});
          else {const next={...value};delete next[kind];onChange(next);}
        }}><option value="">Choose an executor</option>{kind==="image"&&<option value="agent_builtin">This AI&apos;s built-in image tool</option>}<option value="external_handoff">Another app / external handoff</option><option value="api">Connected API service</option><option value="comfyui">Connected ComfyUI workflow</option>{kind==="video"&&<option value="deferred">Decide video later</option>}</select></label>
        {item&&<>
          <label className="fs-label">{title} tool name<input aria-label={`${title} tool name`} value={item.tool_name} onChange={e=>change(kind,{tool_name:e.target.value})}/></label>
          <label className="fs-label">{title} prompt profile<select aria-label={`${title} prompt profile`} value={item.profile} onChange={e=>change(kind,{profile:e.target.value})}>{!profiles.some(p=>p.id===item.profile)&&<option value={item.profile}>{item.profile}</option>}{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label className="fs-label">{title} model version<select aria-label={`${title} model version status`} value={item.model_version_status} onChange={e=>change(kind,{model_version_status:e.target.value as GeneratorSelection["model_version_status"],model:null})}><option value="managed">Managed by the tool</option><option value="unknown">Unknown</option><option value="specified">I know the model/version</option></select></label>
          {item.model_version_status==="specified"&&<label className="fs-label">{title} model<input aria-label={`${title} model`} value={item.model||""} onChange={e=>change(kind,{model:e.target.value})}/></label>}
          {["api","comfyui"].includes(item.executor)?<><label className="fs-label">{title} connection ID<input aria-label={`${title} connection ID`} value={item.connection_id||""} onChange={e=>change(kind,{connection_id:e.target.value||null})}/></label><p>Access and capabilities are verified separately from this saved selection.</p></>:item.executor==="external_handoff"&&<p>A saved external destination is not a verified connection.</p>}
        </>}
        {kind in value&&!item&&<p>Video setup is deferred. Image calibration can continue; video generation will wait.</p>}
      </div>;
    })}
  </fieldset>;
}

export function GeneratorSetup({project,busy,save,imageProfiles,videoProfiles}:{project:Pick<Project,"id"|"revision"|"output_type"|"generation_setup">;busy:boolean;save:(fn:()=>Promise<unknown>)=>Promise<void>;imageProfiles?:Profile[];videoProfiles?:Profile[]}) {
  const confirmed=(kind:"image"|"video")=>["creator_statement","creator_delegation"].includes(project.generation_setup?.[kind]?.selection_source||"");
  const needsSetup=!confirmed("image")||(project.output_type!=="image"&&!confirmed("video")&&project.generation_setup?.video!==null);
  const [editing,setEditing]=useState(needsSetup);
  const [observedNeedsSetup,setObservedNeedsSetup]=useState(needsSetup);
  if(observedNeedsSetup!==needsSetup) {
    setObservedNeedsSetup(needsSetup);
    if(needsSetup) setEditing(true);
  }
  const saved=useMemo<GenerationSetup>(()=>project.generation_setup||{version:1},[project.generation_setup]);
  const form=useDraft(saved,project.revision,"generator-setup:"+project.id);
  const draft=form.draft;
  const [error,setError]=useState("");
  const detailsId=useId();
  return <section className="fs-generator-setup" aria-label="Project generators"><div className="fs-generator-summary"><h2>Project generators</h2><p>{project.generation_setup?.image?.tool_name||"Image generator needed"}{project.output_type!=="image"&&` · ${project.generation_setup?.video?.tool_name||(project.generation_setup?.video===null?"Video deferred":"Video generator needed")}`}</p><button className="fs-button" aria-expanded={editing} aria-controls={detailsId} onClick={()=>setEditing(!editing)}>{editing?"Close generator setup":"Change generator setup"}</button></div>{editing&&<div id={detailsId} className="fs-generator-details">
    <GeneratorSetupFields outputType={project.output_type||"video"} value={draft} onChange={value=>form.edit(()=>value)} imageProfiles={imageProfiles} videoProfiles={videoProfiles}/>
    <DraftNotice {...form}/>
    {error&&<p role="alert">{error}</p>}<button className="fs-primary" disabled={busy||form.conflict} onClick={()=>{setError("");try{const setup=serializeGenerationSetup(project.output_type||"video",draft,project.generation_setup);void save(async()=>{await studioApi("set_generation_setup",{project_id:project.id,expected_revision:form.revision,setup});form.saved();setEditing(false);});}catch(e){setError((e as Error).message);}}}>Save generator setup</button>
  </div>}</section>;
}
