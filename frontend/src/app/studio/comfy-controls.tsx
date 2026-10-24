"use client";
import {useState} from "react";
import {studioApi} from "./client";

export const emptyComfy = {kind:"image",workflow:{},bindings:{positive:{node:"",input:"text"},references:[]},output_node:""};

export function wrapComfyWorkflow(raw:string,kind:string) {
  const parsed=JSON.parse(raw); // Validate shape only; never stringify parsed workflow numbers.
  if(!parsed || typeof parsed!=="object" || Array.isArray(parsed) || parsed.nodes || parsed.links)throw new Error("Use Export API in ComfyUI; canvas JSON cannot be executed directly.");
  return `{"kind":${JSON.stringify(kind)},"workflow":${raw},"bindings":{"positive":{"node":"","input":"text"},"references":[]},"output_node":""}`;
}

export function ComfyWorkflowFields({value,onChange}:{value:string;onChange:(value:string)=>void}) {
  const [error,setError]=useState("");
  return <div>
    <label className="fs-label">Import ComfyUI API workflow<input type="file" accept=".json,application/json" onChange={async e=>{
      const file=e.target.files?.[0]; if(!file)return;
      try {
        if(file.size>2_000_000)throw new Error("Workflow JSON must be at most 2 MB.");
        let kind="image";try{kind=JSON.parse(value).kind==="video"?"video":"image";}catch{}
        onChange(wrapComfyWorkflow(await file.text(),kind));setError("");
      }catch(err){setError((err as Error).message);}
    }}/></label>
    <label className="fs-label">ComfyUI workflow configuration<textarea aria-label="ComfyUI workflow configuration" rows={16} spellCheck={false} value={value} onChange={e=>onChange(e.target.value)}/></label>
    <p className="fs-hint">Import resets mappings for the new workflow. Set kind to image or video and output_node to the file-saving node ID. Map bindings.positive and optional negative to node/input pairs. Map references by Orchestra slot, node and input. An optional seed mapping needs an explicit value. All unmapped model and sampler settings are preserved, including full 64-bit seeds.</p>
    <pre className="fs-config">{`"bindings": {
  "positive": {"node":"6", "input":"text"},
  "negative": {"node":"7", "input":"text"},
  "references": [{"slot":"subject", "node":"10", "input":"image"}]
}`}</pre>
    <p className="fs-hint">Use your installed Qwen, MiniMax H3 or other model workflow. IDs above are examples, not automatic mappings. Each workflow returns one image or MP4. Image reference uploads are supported; video/audio reference uploads need external handoff. Review custom workflow literals before sharing.</p>
    {error&&<p role="alert">{error}</p>}
  </div>;
}

type ComfyConnection={id:string;name:string;adapter?:string;comfy?:{kind:string}};
export function ComfyHandoff({projectId,revision,imageOnly,busy}:{projectId:string;revision:number;imageOnly:boolean;busy:boolean}) {
  const [connections,setConnections]=useState<ComfyConnection[]>([]);
  const [selected,setSelected]=useState("");
  const [result,setResult]=useState<{revision:number;url:string}|null>(null);
  const [error,setError]=useState("");
  const [working,setWorking]=useState(false);
  return <section className="fs-section"><h2>ComfyUI workflow handoff</h2><p className="fs-hint">Configure and validate a mapped workflow in Connections. Direct execution uses Generate via API on a claimed generation task; existing approval and review controls apply.</p>
    <button className="fs-link" disabled={busy||working} onClick={async()=>{setWorking(true);setError("");try{const c=await studioApi<{connections:ComfyConnection[]}>("studio_capabilities");setConnections(c.connections.filter(c=>c.adapter==="comfyui"&&(!imageOnly||c.comfy?.kind==="image")));}catch(e){setError((e as Error).message);}finally{setWorking(false);}}}>Load saved ComfyUI workflows</button>
    <label className="fs-label">ComfyUI workflow<select value={selected} onChange={e=>{setSelected(e.target.value);setResult(null);}}><option value="">Choose a saved workflow</option>{connections.map(c=><option key={c.id} value={c.id}>{c.name} · {c.comfy?.kind}</option>)}</select></label>
    <button className="fs-button" disabled={busy||working||!selected} onClick={async()=>{setWorking(true);setError("");setResult(null);try{const data=await studioApi<{download_url:string;source_revision:number}>("export_comfy_handoff",{project_id:projectId,connection_id:selected});setResult({revision:data.source_revision,url:data.download_url});}catch(e){setError((e as Error).message);}finally{setWorking(false);}}}>Prepare ComfyUI workflow ZIP</button>
    {result&&result.revision===revision&&<a className="fs-link" href={result.url} download="orchestra-comfyui.zip">Download mapped ComfyUI workflows</a>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
