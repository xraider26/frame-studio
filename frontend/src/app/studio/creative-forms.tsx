'use client';
import {useEffect,useId,useRef,useState} from 'react';
import {VisualHelp} from './visual-help';
import type {Technique} from './creative-types';

export function Field({label,value,onChange,placeholder='',multiline=false,type='text',help,entries=[],onApply,options=[],readOnly=false}:{label:string;value:string|number;onChange:(v:string)=>void;placeholder?:string;multiline?:boolean;type?:string;help?:string;entries?:Technique[];onApply?:(entry:Technique)=>void;options?:string[];readOnly?:boolean}){
  const id=useId();
  return <div className="cv-field"><div className="cv-field-label"><label htmlFor={id}>{label}</label>{help&&<VisualHelp label={label} category={help} value={String(value)} entries={entries} onApply={onApply}/>}</div>{multiline?<textarea id={id} rows={3} value={value} readOnly={readOnly} placeholder={placeholder} onChange={e=>onChange(e.target.value)}/>:<input id={id} type={type} value={value} readOnly={readOnly} list={options.length?id+'-choices':undefined} placeholder={placeholder} onChange={e=>onChange(e.target.value)}/>}<datalist id={id+'-choices'}>{options.map(v=><option key={v} value={v}/>)}</datalist></div>;
}

/** Rebase only local changes; keyed collections preserve unrelated remote entries. */
export function reconcile(base:unknown,local:unknown,remote:unknown):unknown {
  if(JSON.stringify(base)===JSON.stringify(local))return remote;
  if(Array.isArray(base)&&Array.isArray(local)&&Array.isArray(remote)&&[...base,...local,...remote].every(v=>v&&typeof v==='object'&&'id' in v)){
    const ids=local.map(v=>v.id);const removed=base.filter(v=>!ids.includes(v.id)).map(v=>v.id);
    const orderChanged=JSON.stringify(base.map(v=>v.id))!==JSON.stringify(ids);
    const order=orderChanged?[...local,...remote.filter(v=>!ids.includes(v.id)&&!removed.includes(v.id))]:remote.filter(v=>!removed.includes(v.id));
    return order.map(v=>{const l=local.find(x=>x.id===v.id),b=base.find(x=>x.id===v.id),r=remote.find(x=>x.id===v.id);return l?reconcile(b,l,r||l):v;});
  }
  if(base&&local&&remote&&typeof base==='object'&&typeof local==='object'&&typeof remote==='object'&&!Array.isArray(local)){
    const b=base as Record<string,unknown>,l=local as Record<string,unknown>,r=remote as Record<string,unknown>;
    return Object.fromEntries([...new Set([...Object.keys(r),...Object.keys(l)])].map(k=>[k,reconcile(b[k],l[k],r[k])]));
  }
  return local;
}

export function useDraft<T>(saved:T,revision:number){
  const [draft,setDraft]=useState(saved),[baseRevision,setRevision]=useState(revision),[dirty,setDirty]=useState(false);
  const base=useRef(saved);
  useEffect(()=>{if(!dirty){setDraft(saved);setRevision(revision);base.current=saved;}},[saved,revision,dirty]);
  const edit=(fn:(current:T)=>T)=>{setDraft(fn);setDirty(true);};
  return {draft,edit,dirty,revision:baseRevision,conflict:dirty&&revision!==baseRevision,
    saved:()=>setDirty(false),reload:()=>{setDraft(saved);base.current=saved;setRevision(revision);setDirty(false);},
    rebase:()=>{setDraft(reconcile(base.current,draft,saved) as T);base.current=saved;setRevision(revision);}};
}

export function DraftNotice({conflict,reload,rebase}:{conflict:boolean;reload:()=>void;rebase:()=>void}){
  return conflict?<div className="cv-conflict" role="alert"><p>The saved project changed. Your draft is preserved. Rebase keeps your edited fields over the latest saved values; reload discards this draft.</p><button className="fs-button" type="button" onClick={rebase}>Rebase my draft</button><button className="fs-link" type="button" onClick={reload}>Reload saved values</button></div>:null;
}

export function PairEditor({label,value,onChange}:{label:string;value:Record<string,string>;onChange:(v:Record<string,string>)=>void}){
  const [key,setKey]=useState('');
  return <div className="cv-pairs"><h3>{label}</h3>{Object.entries(value).map(([k,v])=><div className="cv-pair" key={k}><span>{k}</span><input aria-label={`${label}: ${k}`} value={v} onChange={e=>onChange({...value,[k]:e.target.value})}/><button className="fs-link" type="button" aria-label={`Remove ${label}: ${k}`} onClick={()=>onChange(Object.fromEntries(Object.entries(value).filter(([name])=>name!==k)))}>Remove</button></div>)}<div className="cv-pair"><input aria-label={`New ${label} key`} placeholder="traveler.held_object" value={key} onChange={e=>setKey(e.target.value)}/><button className="fs-button" disabled={!key.trim()||key in value} type="button" onClick={()=>{onChange({...value,[key.trim()]:''});setKey('');}}>Add state</button></div></div>;
}
