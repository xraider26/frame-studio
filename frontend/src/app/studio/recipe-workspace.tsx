"use client";
/* eslint-disable @next/next/no-img-element -- Static generated examples retain their exact framing in the comparison viewer. */
import { useEffect, useId, useRef, useState } from "react";
import { ArrowRight, X } from "lucide-react";
import { studioApi as api } from "./client";
import type { Project, Save } from "./creative-types";
import { ControlModeSwitch, useControlMode } from "./control-mode";
import { RecipeTrials } from "./recipe-trials";

type Citation = {source_id:string;title:string;page:number;lesson_url:string};
type Example = { id: string; title: string; image: string; available?: boolean; prompt?: string; why?: string };
type Role = { id: string; title: string; purpose: string; quality: string[]; sound: string; repair: string; direction: {camera: Record<string,string>; lighting: Record<string,string>} };
export type Recipe = {
  output_type?: "image"|"video"; id: string; name: string; version: number; intent: string; references: string[]; planning: string[];
  decision_requirements: string[]; roles: Role[]; image_checks: string[]; video_checks: string[]; final_checks: string[];
  source_rules: {id: string; section: string; teaching: string; correction: string; provenance: string; grounding?:string; citations?:Citation[]; correction_citations?:Citation[]}[];
  stages: Record<string,string[]>; examples: Example[];
  validation?: {reviewed_outputs:number;passed_outputs:number;ideas:number;models:string[]};
};
type Catalogue = { recipes: Recipe[]; coverage: {review_status: string;page_numbering?:string;verified_sources?:{source_id:string}[]} };
const detailTabs = ["Standards","Workflow","Course rules","Video trials"];

function SourceCitations({items,label}:{items?:Citation[];label:string}) {
  if(!items?.length)return null;
  return <details className="cv-source-citations"><summary>{label} · {items.length} page reference{items.length===1?"":"s"}</summary><ul>{items.map(c=><li key={`${c.source_id}-${c.page}`}><a href={/^https?:\/\//i.test(c.lesson_url)?c.lesson_url:undefined} target="_blank" rel="noopener noreferrer">{c.title} · PDF p. {c.page}<span className="sr-only"> (classroom lesson, opens in a new tab)</span></a></li>)}</ul></details>;
}

function Lines({items}: {items: string[]}) {
  return <ul className="cv-recipe-lines">{items.map(v=><li key={v}>{v}</li>)}</ul>;
}

function ExampleViewer({example, onClose}: {example: Example; onClose:()=>void}) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement | null;
    const overflow=document.body.style.overflow;
    document.body.style.overflow="hidden";
    close.current?.focus();
    return ()=>{document.body.style.overflow=overflow;previous?.focus();};
  },[]);
  return <div className="cv-example-overlay" role="presentation" onClick={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="cv-example-dialog" role="dialog" aria-modal="true" aria-label={example.title} onKeyDown={e=>{
      if(e.key==="Escape")onClose();
      if(e.key==="Tab"){
        const focusable=e.currentTarget.querySelectorAll<HTMLElement>('button,a[href],summary');
        const first=focusable[0],last=focusable[focusable.length-1];
        if(e.shiftKey && document.activeElement===first){e.preventDefault();last?.focus();}
        else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first?.focus();}
      }
    }}>
      <div className="cv-recipe-title"><div><small>ILLUSTRATIVE AI STILL</small><h3>{example.title}</h3></div><button ref={close} className="fs-button" onClick={onClose}><X size={15}/> Close example</button></div>
      <img src={example.image} alt={example.title} />
      <p>{example.why}</p><details><summary>Exact generation prompt</summary><p className="cv-prompt-text">{example.prompt || "Prompt record unavailable."}</p></details>
      <p className="fs-hint">Generated with the built-in image tool. This illustrates visual intent; it does not demonstrate motion, sound, continuity or a tested video pipeline.</p>
    </section>
  </div>;
}

export function RecipeWorkspace({project,busy,save,onNew,outputType}: {project:Project|null;busy:boolean;save:Save;onNew:(id:string)=>void;outputType?:"image"|"video"}) {
  const imageOnly=(outputType || project?.output_type || "video")==="image";
  const detailTabs = imageOnly ? ["Standards","Workflow","Course rules"] : ["Standards","Workflow","Course rules","Video trials"];
  const [catalogue,setCatalogue]=useState<Catalogue|null>(null);
  const [error,setError]=useState("");
  const [selected,setSelected]=useState(project?.template_id || "ai-film");
  const [tab,setTab]=useState("Standards");
  const [example,setExample]=useState<Example|null>(null);
  const [mode,setMode]=useControlMode("recipe");
  const [reload,setReload]=useState(0);
  const tabId=useId();
  useEffect(()=>{let active=true;api<Catalogue>("recipe_catalog").then(v=>{if(active){setCatalogue(v);setError("");}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[reload]);
  const recipes=(catalogue?.recipes || []).filter(r=>(r.output_type || "video")===(imageOnly?"image":"video"));
  const recipe=recipes.find(r=>r.id===selected) || recipes[0];
  const activation=project?.production?.recipe;
  const active=activation?.id===recipe?.id && activation?.version===recipe?.version;
  return <section className="cv-recipe-workspace" aria-label="Course-informed production recipes">
    <div inert={!!example}>
    <div className="cv-recipe-title"><div><div className="fs-eyebrow">PRODUCTION RECIPES</div><h2>Choose the creative approach.</h2><p className="fs-body">Explore the look, directing rules and quality standards before starting.</p></div><ControlModeSwitch mode={mode} onChange={setMode} label="Recipe"/></div>
    {error && <div role="alert">{error} <button className="fs-button" onClick={()=>setReload(n=>n+1)}>Retry recipes</button></div>}
    {!recipe && !error && <p role="status">{catalogue ? "No templates available for this output type." : "Loading production recipes…"}</p>}
    {recipe && <div className="cv-recipe-layout">
      <nav className="cv-recipe-nav" aria-label="Content recipe">{recipes.map((r,i)=><button key={r.id} className={r.id===recipe.id?"active":""} aria-pressed={r.id===recipe.id} onClick={()=>{setSelected(r.id);setExample(null);}}><span>{String(i+1).padStart(2,"0")}</span>{r.name}<ArrowRight size={13}/></button>)}</nav>
      <div className="cv-recipe-detail">
        <div className="cv-recipe-title"><div><small>RECIPE v{recipe.version} · {imageOnly ? "IMAGE PRODUCTION" : "COURSE-INFORMED"}</small><h2>{recipe.name}</h2><p>{recipe.intent}</p></div><button className="fs-primary" disabled={busy} onClick={()=>onNew(recipe.id)}>Use for new project <ArrowRight size={14}/></button></div>
        <div className="cv-recipe-examples">{recipe.examples.map((e,i)=><button className="cv-recipe-example" key={e.id} disabled={!e.available} onClick={()=>setExample(e)} aria-label={`Inspect ${e.title}`}>
          {e.available ? <img src={e.image} alt={e.title} loading="lazy" width={560} height={360}/> : <span className="cv-example-pending">Example not generated</span>}
          <span><small>0{i+1}</small><strong>{e.title}</strong><span className="sr-only">Inspect {e.title}</span></span>
        </button>)}</div>
        <p className="fs-hint">Illustrative AI stills · {imageOnly ? "reference examples, not validated finished outputs" : "not video validation"}. Open an image for its original prompt and the creative choices it demonstrates.</p>
        {!imageOnly && <p className="fs-hint">{recipe.validation?.reviewed_outputs || 0} unique final videos reviewed · {recipe.validation?.ideas || 0} ideas tested. Historical results are scoped to their recipe version, model and settings.</p>}
        {project?.template_id===recipe.id && <div className="cv-recipe-activation"><span>{active?`Active in ${project.name}. Both control modes use these standards.`:`${project.name} keeps its existing settings until you activate this recipe.`}</span>{!active && <button className="fs-button" disabled={busy} onClick={()=>save(async()=>{await api("activate_recipe",{project_id:project.id,expected_revision:project.revision});})}>Activate for {project.name}</button>}</div>}
        <div className="cv-recipe-tabs" role="tablist" aria-label="Recipe details">{detailTabs.map((name,index)=><button key={name} id={`${tabId}-tab-${index}`} role="tab" aria-selected={tab===name} aria-controls={`${tabId}-panel`} tabIndex={tab===name?0:-1} onClick={()=>setTab(name)} onKeyDown={e=>{
          let next=index;
          if(e.key==="ArrowRight")next=(index+1)%detailTabs.length;
          else if(e.key==="ArrowLeft")next=(index+detailTabs.length-1)%detailTabs.length;
          else if(e.key==="Home")next=0;
          else if(e.key==="End")next=detailTabs.length-1;
          else return;
          e.preventDefault();setTab(detailTabs[next]);document.getElementById(`${tabId}-tab-${next}`)?.focus();
        }}>{name}</button>)}</div>
        <div className="cv-recipe-tab-content" id={`${tabId}-panel`} role="tabpanel" aria-labelledby={`${tabId}-tab-${detailTabs.indexOf(tab)}`} tabIndex={0}>
          {tab==="Standards" && <>
            <h3>Prepare these references</h3><Lines items={recipe.references}/><h3>Direct the idea</h3><Lines items={recipe.planning}/>
            {mode==="professional" && <><h3>Agent decision requirements</h3><Lines items={recipe.decision_requirements}/></>}
            <div className="cv-recipe-role-list">{recipe.roles.map((r,i)=><article key={r.id}><small>SHOT ROLE {i+1}</small><h3>{r.title}</h3><p>{r.purpose}</p>{mode==="professional" && <dl><dt>Camera</dt><dd>{Object.values(r.direction.camera).join(" · ") || "Creator-defined"}</dd><dt>Light</dt><dd>{Object.values(r.direction.lighting).join(" · ") || "Creator-defined"}</dd>{!imageOnly && <><dt>Sound</dt><dd>{r.sound}</dd></>}</dl>}<Lines items={r.quality}/><details><summary>If this shot fails</summary><p>{r.repair}</p></details></article>)}</div>
            <div className="cv-recipe-checks"><div><h3>Image acceptance</h3><Lines items={recipe.image_checks}/></div>{!imageOnly && <div><h3>Video acceptance</h3><Lines items={recipe.video_checks}/></div>}</div>
          </>}
          {tab==="Workflow" && <div className="cv-recipe-stage-list">{Object.entries(recipe.stages).map(([stage,items],i)=><article key={stage}><span>{String(i+1).padStart(2,"0")}</span><div><h3>{stage.replaceAll("_"," ")}</h3><Lines items={items}/></div></article>)}<p className="fs-hint">Your stage approval toggles, recorded-check policy, resource limits and chosen tools still govern execution.</p></div>}
          {tab==="Course rules" && <><p className="fs-hint">{catalogue?.coverage.review_status} Shot-role choices and examples are studio-authored adaptations.</p><p className="fs-hint">{catalogue?.coverage.page_numbering || "Page references use PDF file pages."} Lesson links open the classroom, which may require course access; they do not jump to a PDF page. Citations support linked principles, not every instruction or a video quality claim.</p>{recipe.source_rules.map(rule=><article className="cv-source-rule" key={rule.id}><small>{rule.grounding==="original_pages_verified"?"SELECTED ORIGINAL PAGES VERIFIED":"SUPPLIED REVIEW"} · {rule.section}</small><h3>{rule.id.replaceAll("-"," ")}</h3><p>{rule.teaching}</p><SourceCitations items={rule.citations} label="Principle sources"/><p className="cv-rule-correction"><strong>Studio correction: </strong>{rule.correction}</p><SourceCitations items={rule.correction_citations} label="Correction context"/></article>)}</>}
          {tab==="Video trials" && <><h3>Finished-production standard</h3><Lines items={recipe.final_checks}/>{project?.template_id===recipe.id?<RecipeTrials key={project.id} project={project} busy={busy} save={save}/>:<p className="fs-hint">Open a project using this recipe to record a reviewed final production. No finished-video trials are supplied with these image examples.</p>}</>}
        </div>
      </div>
    </div>}
    </div>
    {example && <ExampleViewer example={example} onClose={()=>setExample(null)}/>}
  </section>;
}
