const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const hashes=JSON.parse(fs.readFileSync(path.join(__dirname,'../SOURCE_HASHES.json'),'utf8'));
const changed=Object.entries(hashes).filter(([file,hash])=>!fs.existsSync(file)||crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==hash);
if(changed.length){console.error('Changed source snapshots:',changed.map(([file])=>file));process.exitCode=1;}
else console.log(`PASS: all ${Object.keys(hashes).length} imported source files unchanged`);
