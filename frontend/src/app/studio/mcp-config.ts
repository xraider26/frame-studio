export type McpLaunch = {command:string;args:string[];env?:Record<string,string>;desktop:boolean};

export function mcpConfig(launch:McpLaunch|null|undefined,client:string):string {
  if(!launch)return "Open or connect Orchestra to obtain this machine's MCP configuration.";
  const env={...(launch.env || {}),STUDIO_CLIENT_NAME:client==="Codex"?"codex":client==="Antigravity"?"antigravity":"agent"};
  if(client==="Codex")return `[mcp_servers.frame_studio]\ncommand = ${JSON.stringify(launch.command)}\nargs = ${JSON.stringify(launch.args)}\n\n[mcp_servers.frame_studio.env]\n${Object.entries(env).map(([key,value])=>`${key} = ${JSON.stringify(value)}`).join("\n")}`;
  return JSON.stringify({mcpServers:{frame_studio:{command:launch.command,args:launch.args,env}}},null,2);
}
