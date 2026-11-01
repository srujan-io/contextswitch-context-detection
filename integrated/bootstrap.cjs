const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = __dirname, downloads = path.resolve(root,'../..');
const sources = {
  agent: path.join(downloads,'contextswitch-context-detection/contextswitch-context-detection'),
  cv: path.join(downloads,'contextswitch-cv/contextswitch-cv'),
  voice: path.join(downloads,'contextswitch-kicad_voicecommands/contextswitch-kicad_voicecommands/member3'),
  frontend: path.join(downloads,'contextswitch/screenshot-to-soul-5020'),
};
const excluded = new Set(['.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.output','.tanstack','dist','build','.dist','.agents','.codex','.lovable']);
const hashes = {};
function copy(src,dst) {
  if(fs.statSync(src).isDirectory()) {
    fs.mkdirSync(dst,{recursive:true});
    for(const name of fs.readdirSync(src)) if(!excluded.has(name) && !name.startsWith('.env') && !/\.(pyc|log)$/.test(name)) copy(path.join(src,name),path.join(dst,name));
  } else {
    fs.copyFileSync(src,dst);
    hashes[src]=crypto.createHash('sha256').update(fs.readFileSync(src)).digest('hex');
  }
}
if(fs.existsSync(path.join(root,'backend'))) throw Error('Bootstrap is one-time only; refusing overwrite');
copy(path.join(sources.agent,'backend'),path.join(root,'backend'));
copy(path.join(sources.agent,'extension'),path.join(root,'extension'));
copy(path.join(sources.cv,'vision'),path.join(root,'backend/vision'));
copy(path.join(sources.cv,'models'),path.join(root,'backend/models'));
copy(sources.voice,path.join(root,'backend/voice'));
copy(sources.frontend,path.join(root,'frontend'));
copy(path.join(sources.cv,'extension/content.js'),path.join(root,'extension/gestures.js'));
fs.writeFileSync(path.join(root,'SOURCE_HASHES.json'),JSON.stringify(hashes,null,2));
console.log('Copied source code and model assets only:',Object.keys(hashes).length,'files');
