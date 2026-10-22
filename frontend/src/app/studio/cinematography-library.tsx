"use client";
import { useRef, useState } from "react";
import { ArrowRight, Check, ChevronDown, Columns2, Search } from "lucide-react";
import { studioApi as api } from "./client";
import { mergeRecord, type Catalog, type Direction, type Project, type Save, type Technique } from "./creative-types";
import { TechniqueMedia } from "./visual-help";

const coreCategories = ["camera", "lens", "framing", "movement", "lighting"];
const labels: Record<string, string> = {camera:"Camera looks",lens:"Lenses",framing:"Framing",movement:"Movement",lighting:"Lighting"};
function applyDirection(base: Direction, entry: Technique): Direction {
  return {...mergeRecord(base, entry.apply), technique_ids: [...new Set([...(base.technique_ids || []), ...(entry.apply.technique_ids || []), entry.id])]};
}
function fields(value: unknown, prefix = ""): [string, unknown][] {
  if (value && typeof value === "object" && !Array.isArray(value)) return Object.entries(value).flatMap(([key, item])=>fields(item, prefix ? `${prefix}.${key}` : key));
  return [[prefix,value]];
}
function at(value: unknown, path: string): unknown { return path.split(".").reduce<unknown>((item,key)=>item && typeof item==="object" ? (item as Record<string,unknown>)[key] : undefined,value); }
function display(value: unknown): string { return value === undefined || value === "" || value === null ? "Inherit" : typeof value === "object" ? JSON.stringify(value) : String(value); }

type LibraryProps = {catalog:Catalog|null;project:Project|null;busy:boolean;save:Save};
export function CinematographyLibrary(props: LibraryProps) {
  return <LibraryWorkspace key={props.project?.id || "reference-only"} {...props} />;
}
function LibraryWorkspace({catalog,project,busy,save}: LibraryProps) {
  const [category,setCategory] = useState("");
  const [query,setQuery] = useState("");
  const [chosen,setChosen] = useState("");
  const [comparing,setComparing] = useState(false);
  const [comparison,setComparison] = useState("");
  const [shotId,setShotId] = useState("");
  const [error,setError] = useState("");
  const [status,setStatus] = useState("");
  const [pending,setPending] = useState(false);
  const [appliedRevision,setAppliedRevision] = useState("");
  const inFlight = useRef(false);
  const categories = [...new Set([...coreCategories,...(catalog?.categories || [])])];
  const entries = catalog?.entries || [];
  const activeCategory = category || (entries.some(e=>e.category==="camera") ? "camera" : entries[0]?.category) || "camera";
  const visible = entries.filter(e=>e.category===activeCategory && `${e.name} ${e.explanation} ${e.use_when}`.toLowerCase().includes(query.toLowerCase()));
  const entry = visible.find(e=>e.id===chosen) || visible[0];
  const group = entry?.visual.sample?.comparison_group;
  const peers = entry ? entries.filter(e=>e.category===entry.category && e.id!==entry.id && (group ? e.visual.sample?.comparison_group===group : !!entry.visual.motion && !!e.visual.motion)) : [];
  const other = peers.find(e=>e.id===comparison) || peers[0];
  const shot = project?.shots.find(s=>s.id===shotId);
  const locked = busy || pending || appliedRevision === `${project?.id}:${project?.revision}`;
  async function apply(scope: "shot" | "defaults") {
    if (!project || !entry || inFlight.current || locked || (scope === "shot" && !shot)) return;
    const snapshot=project, technique=entry, target=shot;
    inFlight.current=true;setPending(true);setError("");setStatus("");
    try {
      await save(async()=>{
        try {
          if(scope === "shot" && target) {
            await api("update_shots",{project_id:snapshot.id,expected_revision:snapshot.revision,shots:snapshot.shots.map(s=>s.id===target.id?{...s,direction:applyDirection(s.direction,technique)}:s)});
          } else {
            await api("update_production",{project_id:snapshot.id,expected_revision:snapshot.revision,production:{...snapshot.production,defaults:applyDirection(snapshot.production.defaults,technique)}});
          }
          setAppliedRevision(`${snapshot.id}:${snapshot.revision}`);
          setStatus(`${technique.name} applied to ${scope === "shot" ? target?.title : "project defaults"}.`);
        } catch(e) { setError(e instanceof Error ? e.message : "The technique could not be saved. Try again after refreshing the project.");throw e; }
      });
    } catch(e) { setError(e instanceof Error ? e.message : "The technique could not be saved."); }
    finally {inFlight.current=false;setPending(false);}
  }
  function choose(id:string) {setChosen(id);setError("");setStatus("");}
  if(!catalog) return <section className="cl-library"><div className="cl-heading"><p className="fs-eyebrow">VISUAL REFERENCE</p><h1>Cinematography library</h1><p>Loading the technique library…</p></div></section>;
  return <section className="cl-library" aria-label="Cinematography library">
    <header className="cl-heading"><div><p className="fs-eyebrow">VISUAL REFERENCE / DIRECTION</p><h1>Cinematography library<span>.</span></h1><p>Explore the image. Compare the choices. Set your direction.</p></div><div className="cl-catalog-note"><span>{entries.length.toString().padStart(2,"0")}</span><small>techniques<br/>to explore</small></div></header>
    <div className="cl-toolbar"><nav className="cl-categories" aria-label="Technique categories">{categories.map(c=><button type="button" key={c} aria-pressed={activeCategory===c} onClick={()=>{setCategory(c);setChosen("");setComparing(false);setError("");setStatus("");}}>{labels[c] || c}</button>)}</nav><label className="cl-search"><Search size={15}/><span className="sr-only">Search techniques</span><input aria-label="Search techniques" placeholder="Search techniques" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
    {entry ? <>
      <div className="cl-stage">
        <div className="cl-viewer"><div className="cl-viewer-top"><span>{comparing && other ? "COMPARE / SAME REFERENCE SCENE" : `${(labels[activeCategory] || activeCategory).toUpperCase()} / VISUAL STUDY`}</span><button type="button" aria-pressed={comparing} disabled={!peers.length} onClick={()=>setComparing(!comparing)}><Columns2 size={15}/>{comparing?"Single view":"Compare looks"}</button></div>
          <div className={`cl-media-layout ${comparing && other ? "is-comparing" : ""}`}><div><TechniqueMedia key={entry.id} entry={entry}/>{comparing && other && <p className="cl-comparison-name"><span>A</span>{entry.name}</p>}</div>{comparing && other && <div><TechniqueMedia key={other.id} entry={other}/><label className="cl-comparison-name"><span>B</span><select aria-label="Compare with" value={other.id} onChange={e=>setComparison(e.target.value)}>{peers.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><ChevronDown size={14}/></label></div>}</div>
          {comparing && other && <p className="cl-comparison-note">Same reference scene · {entry.visual.motion ? "shared spatial scene" : "generated stills"}. {entry.visual.sample ? "Individual AI examples may vary beyond the selected technique." : "Scrub each demonstration to inspect the movement."}</p>}
          <details className="cl-provenance"><summary>{entry.visual.sample?"About this generated image":"About this visual study"}</summary><p>{entry.visual.sample?.caption || "An illustrative spatial reference for exploring visual intent."}</p>{entry.visual.sample && <><p>This still illustrates a look; it does not guarantee the result of a video generation.</p><strong>Image prompt</strong><p>{entry.visual.sample.prompt}</p></>}<p>{entry.source_note}</p></details>
        </div>
        <aside className="cl-inspector"><p className="fs-eyebrow">{entry.category} / {String(visible.indexOf(entry)+1).padStart(2,"0")}</p><h2>{entry.name}</h2><p className="cl-explanation">{entry.explanation}</p><dl className="cl-guidance"><div><dt>Use it for</dt><dd>{entry.use_when}</dd></div><div><dt>Watch for</dt><dd>{entry.risk}</dd></div><div><dt>A safer alternative</dt><dd>{entry.safer_alternative}</dd></div></dl><details className="cl-sources"><summary>Sources & context</summary><p>{entry.source} · {entry.section}</p><p>{entry.source_note}</p><small>{entry.provenance}</small>{entry.citations?.map(c=><p key={`${c.source_id}-${c.page}`}><a href={/^https?:\/\//i.test(c.lesson_url)?c.lesson_url:undefined} target="_blank" rel="noopener noreferrer">{c.title} · PDF p. {c.page}</a></p>)}</details></aside>
      </div>
      <div className="cl-strip-heading"><h2>Explore {labels[activeCategory]?.toLowerCase() || activeCategory}</h2><small>{visible.length} {visible.length===1?"technique":"techniques"} · select to preview</small></div>
      <div className="cl-filmstrip" aria-label={`${activeCategory} techniques`}>{visible.map(e=><button type="button" key={e.id} className={`cl-technique ${entry.id===e.id?"is-selected":""}`} aria-label={e.name} aria-pressed={entry.id===e.id} onClick={()=>choose(e.id)}><div className="cl-thumbnail"><TechniqueMedia compact entry={e}/>{entry.id===e.id && <span className="cl-selected-marker"><Check size={14}/></span>}</div><span className="cl-technique-title">{e.name}<ArrowRight size={14}/></span></button>)}</div>
      <section className="cl-apply" aria-label="Apply selected technique"><div className="cl-apply-heading"><div><p className="fs-eyebrow">SET DIRECTION</p><h2>Apply {entry.name}</h2></div><span className="cl-revision">{project?`${project.name} · revision ${project.revision}`:"Open a project to apply"}</span></div><p className="cl-apply-intro">Only the fields below change. Browsing and comparing do not change your project.</p>
        {project ? <><label className="cl-target">Target shot<select aria-label="Target shot" value={shot?.id || ""} disabled={pending} onChange={e=>{setShotId(e.target.value);setError("");setStatus("");}}><option value="">Choose a shot…</option>{project.shots.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
          <div className="cl-changes"><table><caption>Changed fields preview</caption><thead><tr><th>Field</th><th>{shot?shot.title:"Choose a shot"}</th><th>Project defaults</th></tr></thead><tbody>{[...fields(entry.apply).filter(([key])=>key!=="technique_ids"),["technique_ids",null] as [string,unknown]].map(([key,value])=><tr key={key}><th>{key}</th><td>{shot?<><span>{display(at(shot.direction,key))}</span><ArrowRight size={12}/><strong>{display(key==="technique_ids"?applyDirection(shot.direction,entry).technique_ids:value)}</strong></>:<span>Choose a target</span>}</td><td><span>{display(at(project.production.defaults,key))}</span><ArrowRight size={12}/><strong>{display(key==="technique_ids"?applyDirection(project.production.defaults,entry).technique_ids:value)}</strong></td></tr>)}</tbody></table></div>
          <div className="cl-apply-actions"><div><button type="button" className="fs-primary" disabled={locked || !shot} onClick={()=>apply("shot")}>Apply to shot<ArrowRight size={15}/></button><button type="button" className="fs-button" disabled={locked} onClick={()=>apply("defaults")}>Apply as project defaults</button></div><p>Project defaults preserve existing shot overrides. Reuse a finished look through saved templates.</p></div>
          <p role="status" className="cl-save-status">{pending?"Saving direction…":status}</p>{error && <p role="alert" className="cl-save-error">{error} Your selected technique is still available; refresh the project if its revision changed.</p>}
        </>:<p className="cl-empty">Create or open a project to apply a technique to a shot or its defaults.</p>}
      </section>
    </>:<div className="cl-empty"><h2>No techniques found</h2><p>Try a different category or search.</p><button type="button" className="fs-button" onClick={()=>setQuery("")}>Clear search</button></div>}
    <footer className="cl-coverage">{catalog.coverage.status} · {catalog.coverage.limitations}</footer>
  </section>;
}
