'use strict';
const path=require('node:path');

function mcpCopyItems(resources,dataDir,copy) {
 const command=path.join(resources,'backend','FrameStudioService.exe');
 const args=['mcp','--data-dir',dataDir];
 return [['Codex (TOML)','codex'],['Cursor (JSON)','cursor'],['Claude Desktop (JSON)','claude'],['Antigravity (JSON)','antigravity']].map(([label,client])=>({label,click(){
  const env={STUDIO_CLIENT_NAME:client};
  const text=client==='codex'
   ? `[mcp_servers.frame_studio]\ncommand = ${JSON.stringify(command)}\nargs = ${JSON.stringify(args)}\n\n[mcp_servers.frame_studio.env]\nSTUDIO_CLIENT_NAME = "codex"\n`
   : JSON.stringify({mcpServers:{frame_studio:{command,args,env}}},null,2);
  copy(text);
 }}));
}
module.exports={mcpCopyItems};
