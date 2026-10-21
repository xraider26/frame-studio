export type Asset = {id:string;url:string;path:string;kind:string;stale:boolean;role?:string;name?:string;version?:number;shot_id?:string;review?:TakeReview;required_checks?:string[]};
export type TakeReview = {criteria:Record<string,boolean>;notes:string;defect:string;actor:string;at:string;inspected:string[]};
export type Direction = {
  scene_id:string;story_purpose:string;script_beat:string;environment:string;mood:string;generation_mode:string;
  camera:Record<string,string>;lighting:Record<string,string>;art:Record<string,string>;
  action:{opening:string;primary_action:string;ending:string;beats:{start:number;end:number;description:string}[];state_before:Record<string,string>;state_after:Record<string,string>;transition:string;continuity_from:string;visible_entities:string[];headcount:number|null};
  sound:{speaker_id:string;dialogue:string;voice:string;measured_seconds:number|null;pauses_seconds:number|null;ambience:string;foley:string;music:string;captions:string;cutaway:boolean|null};
  references:{slot:string;asset_id:string;version:number;role:string;entity_id:string;notes:string}[];
  quality:{criteria:string[];known_defect:string;revision_reason:string};technique_ids:string[];
};
export type Shot = {id:string;_draft_key?:string;title:string;image_prompt:string;motion_prompt:string;narration:string;duration_seconds:number;edit_duration_seconds:number;image_asset:string|null;video_asset:string|null;direction:Direction};
export type Entity = {id:string;kind:string;name:string;version:number;identity:string;wardrobe:string;voice:string;layout:string;light_sources:string;materials:string;asset_ids:string[]};
export type StoryBeat = {id:string;title:string;duration_seconds:number;narration:string;dialogue:string;action:string;captions:string;measured_seconds:number|null;fact_or_dramatization:string};
export type Resources = {unit:string;limit:number|null;pilot_limit:number|null;max_attempts_per_shot:number|null;image_cost:number|null;video_cost:number|null;cost_evidence:string};
export type Production = {
  brief:Record<string,string>;story:{hooks:string[];selected_hook:string;framework:string;beats:StoryBeat[]};
  bible:Entity[];defaults:Direction;capabilities:{model:string;confirmed:boolean;source:string;observed_at:string;modes:string[];durations:number[];aspects:string[];max_references:number|null;audio:boolean|null};
  resources:Resources;require_recorded_checks:boolean;format_rules:string[];
  experiments:{id:string;variable:string;hypothesis:string;result:string;source_date:string;impressions:number|null;ctr_percent:number|null;completion_percent:number|null}[];
};
export type Issue = {rule:string;severity:string;shot_id:string|null;path:string;message:string};
export type Preflight = {issues:Issue[];errors:number;warnings:number;retained_seconds:number;scope:string};
export type Action = {action:string;step:string;message:string;kind?:string;shot_id?:string};
export type Job = {id:string;status:string;kind:string;shot_id:string;error?:string;asset_id?:string;handoff:Record<string,unknown>;cost?:{planned:number|null;actual:number|null;unit:string;evidence:string}};
export type Project = {id:string;name:string;template_id:string;revision:number;settings:Record<string,string|number>;approval_policy:Record<string,boolean>;steps:Record<string,{ready:boolean;status:string}>;documents:Record<string,{text:string}>;shots:Shot[];assets:Asset[];jobs:Job[];history:{at:string;type:string;actor:string;message:string}[];next_action:Action;production:Production;preflight:Preflight};
export type Technique = {id:string;category:string;name:string;explanation:string;use_when:string;risk:string;safer_alternative:string;source:string;section:string;source_note:string;provenance:string;apply:Partial<Direction>;visual:{kind:string;variant:string}};
export type Catalog = {entries:Technique[];categories:string[];coverage:{status:string;limitations:string;entry_count:number;full_original_catalogues:boolean}};
export type Save = (fn:()=>Promise<unknown>)=>Promise<void>;

export const emptyDirection = ():Direction => ({scene_id:'',story_purpose:'',script_beat:'',environment:'',mood:'',generation_mode:'inherit',camera:{},lighting:{},art:{},action:{opening:'',primary_action:'',ending:'',beats:[],state_before:{},state_after:{},transition:'',continuity_from:'',visible_entities:[],headcount:null},sound:{speaker_id:'',dialogue:'',voice:'',measured_seconds:null,pauses_seconds:null,ambience:'',foley:'',music:'',captions:'',cutaway:null},references:[],quality:{criteria:[],known_defect:'',revision_reason:''},technique_ids:[]});

export function mergeRecord<T>(base:T, patch:Partial<T>):T {
  const result = {...base};
  for (const key in patch) {
    const value = patch[key];
    if (value && typeof value === 'object' && !Array.isArray(value)) result[key] = mergeRecord(base[key] || {} as T[typeof key], value);
    else result[key] = value as T[typeof key];
  }
  return result;
}
