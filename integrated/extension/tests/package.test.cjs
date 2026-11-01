const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
test('popup and all declared Chrome icon sizes are present and valid PNGs',()=>{
 const root=path.join(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
 assert.equal(manifest.action.default_popup,'ui/extension.html');
 assert.ok(fs.existsSync(path.join(root,manifest.action.default_popup)));
 assert.equal(manifest.content_scripts,undefined);
 assert.ok(!manifest.host_permissions.includes('<all_urls>'));
 assert.ok(manifest.optional_host_permissions.includes('https://kicanvas.org/*'));
 for(const size of [16,32,48,128]){
  assert.equal(manifest.icons[size],manifest.action.default_icon[size]);
  const data=fs.readFileSync(path.join(root,manifest.icons[size]));
  assert.equal(data.subarray(1,4).toString(),'PNG');
  assert.equal(data.readUInt32BE(16),size);assert.equal(data.readUInt32BE(20),size);
 }
});
