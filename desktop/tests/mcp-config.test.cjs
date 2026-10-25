const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');

test('copy menu offers named clients and copies installed paths in their actual formats',()=>{
 const {mcpCopyItems}=require('../mcp-config.cjs');
 const copied=[];
 const resources=path.resolve('install with spaces','Orchestra','resources');
 const data=path.resolve('existing creator data');
 const items=mcpCopyItems(resources,data,value=>copied.push(value));
 assert.deepEqual(items.map(item=>item.label),['Codex (TOML)','Cursor (JSON)','Claude Desktop (JSON)','Antigravity (JSON)']);
 for(const item of items)item.click();
 assert.match(copied[0],/^\[mcp_servers\.frame_studio\]/);
 assert.ok(copied[0].includes(`command = ${JSON.stringify(path.join(resources,'backend','FrameStudioService.exe'))}`));
 assert.ok(copied[0].includes(`args = ${JSON.stringify(['mcp','--data-dir',data])}`));
 assert.match(copied[0],/STUDIO_CLIENT_NAME = "codex"/);
 for(const [index,client] of [[1,'cursor'],[2,'claude'],[3,'antigravity']]){
  const config=JSON.parse(copied[index]).mcpServers.frame_studio;
  assert.equal(config.command,path.join(resources,'backend','FrameStudioService.exe'));
  assert.deepEqual(config.args,['mcp','--data-dir',data]);
  assert.equal(config.env.STUDIO_CLIENT_NAME,client);
  assert.doesNotMatch(copied[index],/agent.token|browser.token|Bearer/);
 }
});
