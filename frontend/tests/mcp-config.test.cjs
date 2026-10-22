const {test}=require('node:test');const assert=require('node:assert/strict');const {spawnSync}=require('node:child_process');const path=require('node:path');
const out=path.resolve(__dirname,'../.studio-test/mcp-config');
const built=spawnSync(process.execPath,[require.resolve('typescript/bin/tsc'),'src/app/studio/mcp-config.ts','--outDir',out,'--module','commonjs','--target','ES2022','--skipLibCheck'],{cwd:path.resolve(__dirname,'..'),encoding:'utf8'});
assert.equal(built.status,0,built.stdout+built.stderr);
const {mcpConfig}=require(path.join(out,'mcp-config.js'));
const launch={command:'C:\\Users\\Creator Name\\Frame Studio\\FrameStudioService.exe',args:['mcp','--data-dir','C:\\Users\\Creator Name\\AppData\\Frame Studio'],env:{},desktop:true};
test('desktop configuration uses installed executable and explicit data location',()=>{const config=JSON.parse(mcpConfig(launch,'Claude Desktop')).mcpServers.frame_studio;assert.equal(config.command,launch.command);assert.deepEqual(config.args,launch.args);assert.equal(config.env.STUDIO_CLIENT_NAME,'agent');assert.doesNotMatch(JSON.stringify(config),/G:\/AI|studio_mcp\.py/);});
test('Codex TOML escapes Windows paths and retains argument boundaries',()=>{const text=mcpConfig(launch,'Codex');assert.ok(text.includes(`command = ${JSON.stringify(launch.command)}`));assert.ok(text.includes(`args = ${JSON.stringify(launch.args)}`));assert.match(text,/STUDIO_CLIENT_NAME = "codex"/);});
test('unconnected backend does not invent a machine-specific command',()=>{assert.match(mcpConfig(null,'Codex'),/Connect|Open/);assert.doesNotMatch(mcpConfig(null,'Codex'),/python|G:\//);});
