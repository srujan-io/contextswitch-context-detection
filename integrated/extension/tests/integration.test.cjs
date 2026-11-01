const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function gestures(){
 const messages=[],listeners=[],timers=[],target={style:{},dispatchEvent:e=>messages.push(e),closest(){return this},contains(){return true},click(){messages.push({type:'click'})},getBoundingClientRect:()=>({left:0,top:0,width:800,height:600})};
 const document={createElement:()=>({...target,style:{}}),documentElement:{appendChild(){}},elementFromPoint:()=>target,querySelector:()=>target,body:target};
 class Event{constructor(type,options){Object.assign(this,{type},options)}}
 const context=vm.createContext({document,window:{innerWidth:800,innerHeight:600},console:{log(){}},chrome:{runtime:{onMessage:{addListener:f=>listeners.push(f)},sendMessage:(m,cb)=>cb?.({connected:true})}},setInterval:f=>timers.push(f),setTimeout:()=>1,clearTimeout(){},HTMLElement:class{},PointerEvent:Event,MouseEvent:Event,WheelEvent:Event,Date,Math,Number});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../gestures.js'),'utf8'),context);
 return{messages,send:event=>listeners.forEach(f=>f({type:'CONTEXTSWITCH_CV',event})),timers};
}
test('six legacy head events retain signed canvas pan/zoom behavior',()=>{
 const g=gestures();for(const action of ['HEAD_UP','HEAD_DOWN','HEAD_LEFT','HEAD_RIGHT','HEAD_TILT_LEFT','HEAD_TILT_RIGHT'])g.send({source:'HEAD',action});
 const wheel=g.messages.filter(e=>e.type==='wheel');assert.equal(wheel.length,6);
 assert.deepEqual(wheel.map(e=>[e.deltaX,e.deltaY,e.ctrlKey]),[[0,-180,false],[0,180,false],[-180,0,false],[180,0,false],[0,180,true],[0,-180,true]]);
});
test('hand scroll dispatches a bounded vertical wheel and cancels held click',()=>{
 const g=gestures();g.send({source:'HAND',action:'CURSOR_MOVE',parameters:{x:.5,y:.5}});
 g.send({source:'HAND',action:'PINCH_START'});
 g.send({source:'HAND',action:'SCROLL',parameters:{delta_y:40}});
 g.send({source:'HAND',action:'PINCH_END'});
 assert.equal(g.messages.filter(e=>e.type==='click').length,0);
 assert.equal(g.messages.find(e=>e.type==='wheel').deltaY,40);
});
test('pinch click works; tracking loss, zoom and agent cancellation never click',()=>{
 const g=gestures(),hand=(action,parameters={})=>g.send({source:'HAND',action,parameters});
 hand('CURSOR_MOVE',{x:.5,y:.5});hand('PINCH_START');hand('PINCH_END');assert.equal(g.messages.filter(e=>e.type==='click').length,1);
 hand('PINCH_START');hand('TRACKING_LOST');hand('PINCH_END');assert.equal(g.messages.filter(e=>e.type==='click').length,1);
 hand('CURSOR_MOVE',{x:.5,y:.5});hand('PINCH_START');hand('PINCH_CANCEL');hand('PINCH_ZOOM_START');hand('PINCH_END');hand('PINCH_ZOOM',{delta:.2});
 const before=g.messages.filter(e=>e.type==='wheel').length;g.send({source:'HEAD',action:'HEAD_TILT_RIGHT'});assert.equal(g.messages.filter(e=>e.type==='wheel').length,before);
 hand('PINCH_ZOOM_END');assert.equal(g.messages.filter(e=>e.type==='click').length,1);
});
function worker(shared={},consented=true){
 if(consented && !shared["contextswitch.pageConsent.v1"])shared["contextswitch.pageConsent.v1"]={approved:true,origins:["https://kicanvas.org/*"]};
 const calls=[],sent=[],handlers={},storage=shared,queue=[];
 const ev=()=>({addListener:f=>{}});
 const chrome={permissions:{contains:async()=>consented,remove:async()=>true,onRemoved:ev()},scripting:{unregisterContentScripts:async()=>{},registerContentScripts:async()=>{},executeScript:async()=>{}},storage:{local:{get:async key=>({[key]:storage[key]}),set:async obj=>Object.assign(storage,obj)}},tabs:{query:async()=>[{id:7,url:'https://kicanvas.org/'}],get:async id=>({id,url:'https://kicanvas.org/'}),sendMessage:async(id,m)=>{sent.push({id,m});return m.type==='REQUEST_CONTEXT'?{context:{url:'https://kicanvas.org/',title:'Schematic'}}:m.type==='EXECUTE_ACTION'?{status:'UNVERIFIED',verified:false}:{};},onActivated:ev(),onUpdated:ev(),onRemoved:ev()},runtime:{onConnect:ev(),onMessage:{addListener:f=>handlers.message=f},onInstalled:ev(),onStartup:ev()},alarms:{create(){},onAlarm:ev()}};
 class WS{static OPEN=1;constructor(){this.readyState=1;WS.last=this;}send(){}close(){this.readyState=3;this.onclose?.();}}
 const context=vm.createContext({chrome,URL,importScripts:name=>vm.runInContext(fs.readFileSync(path.join(__dirname,'..',name),'utf8'),context),WebSocket:WS,AbortSignal,Date,console,setInterval(){},fetch:async(url,opts={})=>{calls.push({url,opts});const data=url.includes('/actions/next')?{action:queue.shift()||null}:url.includes('/context/update')?{context:JSON.parse(opts.body)}:url.includes('/system/state')?{sensors:{}}:{};return{ok:true,json:async()=>data};}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../background.js'),'utf8'),context);
 return{calls,sent,queue,WS,context,shared:storage,async settle(){for(let i=0;i<30;i++)await new Promise(r=>setImmediate(r));},run:()=>vm.runInContext('tick()',context)};
}
test('worker merges top-level tab context, queues by tab and reports truthful results',async()=>{
 const w=worker();await w.settle();
 w.queue.push({action_id:'a1',tab_id:7,action:'zoom_in'});await w.run();
 const ctx=w.calls.find(c=>c.url.endsWith('/context/update'));assert.equal(JSON.parse(ctx.opts.body).tab_id,7);
 assert.ok(w.calls.some(c=>c.url.includes('/actions/next?tab_id=7')));
 const executions=w.sent.filter(s=>s.m.type==='EXECUTE_ACTION');assert.equal(executions.length,1);assert.equal(executions[0].id,7);
 const result=w.calls.find(c=>c.url.endsWith('/actions/result'));assert.equal(JSON.parse(result.opts.body).status,'UNVERIFIED');
 w.queue.push({action_id:'a1',tab_id:7,action:'zoom_in'});await w.run();assert.equal(w.sent.filter(s=>s.m.type==='EXECUTE_ACTION').length,1);
});
test('without explicit consent the worker makes no backend request or page read',async()=>{
 const w=worker({},false);await w.settle();await w.run();
 assert.equal(w.calls.length,0);assert.equal(w.sent.length,0);assert.equal(w.WS.last,undefined);
});
test('revoking consent stops page reads and cancels previous queued work',async()=>{
 const w=worker();await w.settle();
 await vm.runInContext('revokePages()',w.context);
 const count=w.sent.length;await w.run();assert.equal(w.sent.length,count);
 assert.equal(w.shared['contextswitch.pageConsent.v1'].approved,false);
 assert.ok(w.calls.some(c=>c.url.endsWith('/system/browser/revoke')));
});
test('worker reconnect rejects stale gestures and persistent attempt marker prevents replay',async()=>{
 const w=worker({executedActions:{old:Date.now()}});await w.settle();
 w.queue.push({action_id:'old',tab_id:7,action:'zoom_in'});await w.run();assert.equal(w.sent.filter(s=>s.m.type==='EXECUTE_ACTION').length,0);
 const before=w.sent.length;await w.WS.last.onmessage({data:JSON.stringify({source:'HAND',action:'PINCH_START',timestamp:1})});assert.equal(w.sent.length,before);
 await w.WS.last.onmessage({data:JSON.stringify({source:'HAND',action:'CURSOR_MOVE',parameters:{x:.5,y:.5},timestamp:Date.now()})});assert.equal(w.sent.length,before+1);
 w.WS.last.close();await w.run();assert.equal(w.WS.last.readyState,1);
});



