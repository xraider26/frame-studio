import type {GenerationSetup} from "./creative-types";

export function serializeGenerationSetup(outputType:string, draft:GenerationSetup, previous?:GenerationSetup):GenerationSetup {
  const setup:GenerationSetup={version:1};
  for(const kind of (["image",...(outputType==="image"?[]:["video"])] as ("image"|"video")[])) {
    const item=draft[kind];
    if(previous && JSON.stringify(item)===JSON.stringify(previous[kind]) && (!item || ["creator_statement","creator_delegation"].includes(item.selection_source))) continue;
    if(!item) {if(kind==="image") throw new Error("Choose an image generator first.");if(!(kind in draft)) throw new Error("Choose a video generator or explicitly decide video later.");setup[kind]=null;continue;}
    if(!item.tool_name.trim()) throw new Error(`Name the ${kind} tool.`);
    if(item.model_version_status==="specified"&&!item.model?.trim()) throw new Error(`Supply the ${kind} model or choose managed/unknown.`);
    setup[kind]={...item,model:item.model_version_status==="specified"?item.model:null,selection_source:"creator_statement",source_text:`Creator selected ${kind}: ${item.tool_name} (${item.executor}); ${item.model_version_status}${item.model?" · "+item.model:""}.`};
  }
  return setup;
}

export function generatorSettings(
  outputType: string,
  values: {
    image_generator: string;
    image_model: string;
    video_generator: string;
    video_model: string;
  },
) {
  return outputType === "image"
    ? {
        image_generator: values.image_generator,
        image_model: values.image_model,
      }
    : { ...values };
}
