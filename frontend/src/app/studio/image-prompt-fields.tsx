"use client";

import type {ImageRequirements} from "./creative-types";
export const emptyImageRequirements = (): ImageRequirements => ({mode:"generate",instructions:"",preserve:"",exact_text:[],layout:"",background:""});

export function ImagePromptFields({value,onChange}:{value:ImageRequirements;onChange:(value:ImageRequirements)=>void}) {
  return <fieldset className="cv-form-grid"><legend>Image generation & editing</legend>
    <label className="fs-label">Image operation<select value={value.mode} onChange={e=>onChange({...value,mode:e.target.value as ImageRequirements["mode"]})}><option value="generate">Generate an image</option><option value="edit">Edit supplied reference image</option></select></label>
    {([['instructions','Requested image changes / requirements'],['preserve','What must stay unchanged'],['layout','Layout / text placement'],['background','Background / transparency intent']] as const).map(([key,label])=><label className="fs-label" key={key}>{label}<textarea aria-label={label} value={value[key]} onChange={e=>onChange({...value,[key]:e.target.value})}/></label>)}
    <label className="fs-label">Exact visible text (one item per line)<textarea aria-label="Exact visible text (one item per line)" value={value.exact_text.join('\n')} onChange={e=>onChange({...value,exact_text:e.target.value.split('\n')})}/></label>
    <p className="fs-hint">Bind source images and their roles in References. Check the actual output for text, identity and layout fidelity. Transparency also needs an RGBA-capable workflow. Custom prompt templates remain under your control.</p>
  </fieldset>;
}
