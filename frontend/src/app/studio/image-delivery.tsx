"use client";
import type {Project} from "./creative-types";
import {useState} from "react";
import {Download} from "lucide-react";
import {studioApi as api} from "./client";
export function ImageDelivery({project}:{project:Project}) {
 const [bundle,setBundle]=useState<{download_url:string;revision:number}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const selected=project.shots.flatMap(shot=>{const asset=project.assets.find(a=>a.id===shot.image_asset&&!a.stale&&a.kind==="image");return asset?[{shot,asset}]:[];});
 return <section className="fs-image-delivery"><div className="fs-eyebrow">EXPORT</div><h1>Image handoff</h1><p className="fs-lead">Download your selected images or prepare a portable package with prompts, references and the saved project plan.</p>
  <div className="fs-delivery-images">{selected.map(({shot,asset})=><a key={shot.id} href={asset.url} download><img src={asset.url} alt={shot.title}/><span>{shot.title}<Download size={14}/></span></a>)}</div>
  {!selected.length&&<p className="fs-body">Select a returned image in Review to include it here.</p>}
  {error&&<p role="alert">{error}</p>}
  <button className="fs-primary" disabled={busy} onClick={async()=>{setBusy(true);setError("");try{const result=await api<{download_url:string}>("export_handoff",{project_id:project.id});setBundle({...result,revision:project.revision});}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}><Download size={15}/>{busy?"Preparing package…":"Prepare portable package"}</button>
  {bundle?.revision===project.revision&&<a className="fs-button fs-delivery-download" href={bundle.download_url} download="studio-image-handoff.zip">Download handoff ZIP <Download size={15}/></a>}
 </section>;
}
