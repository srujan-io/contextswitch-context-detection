/* MV3 worker: WS keepalive + alarms + content heartbeat restore after suspension. */
importScripts('privacy.js');
const API='http://127.0.0.1:8001';
let socket, ticking=false, lastPing=0;
const ports=new Set(),busy=new Set();
const supported=url=>/^https:\/\/([a-z0-9-]+\.)*(kicanvas\.org|youtube\.com)\//i.test(url||'');
async function api(path,body) {
 const r=await fetch(API+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(path==='/voice/listen'?25000:12000)});
 const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));return data;
}
const sendUi=message=>{for(const p of ports){try{p.postMessage(message);}catch{ports.delete(p);}}};
async function cancelAll(){if(!pageConsent)return;const tabs=await chrome.tabs.query({});await Promise.allSettled(tabs.filter(t=>permittedUrl(t.url)).map(t=>chrome.tabs.sendMessage(t.id,{type:'CONTEXTSWITCH_CV',event:{source:'HAND',action:'TRACKING_LOST'}})));}
function connect(){
 if(!pageConsent)return;
 if(socket&&socket.readyState<2)return;
 socket=new WebSocket('ws://127.0.0.1:8001/ws/cv');const current=socket;
 current.onopen=()=>{void cancelAll();sendUi({type:'CONNECTION_STATUS',status:'connected'});};
 current.onmessage=async({data})=>{
  if(socket!==current||!pageConsent)return;let event;try{event=JSON.parse(data);}catch{return;}sendUi(event);
  if(event.type==='SENSOR_STATUS'&&event.sensor==='CAMERA'&&event.status!=='TRACKING'){await cancelAll();return;}
  if(event.type==='ACTION_READY' && Number.isInteger(event.tab_id)){await runAction(event.tab_id);return;}
  if(!['HEAD','HAND'].includes(event.source))return;
  if(!Number.isFinite(event.timestamp)||Date.now()-event.timestamp>700||event.timestamp>Date.now()+100)return;
  const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
  if(!tab?.id||!permittedUrl(tab.url)||busy.has(tab.id))return;
  chrome.tabs.sendMessage(tab.id,{type:'CONTEXTSWITCH_CV',event}).catch(()=>{});
 };
 current.onclose=()=>{if(socket===current)socket=null;void cancelAll();sendUi({type:'CONNECTION_STATUS',status:'disconnected'});};
 current.onerror=()=>current.close();
}
async function sync(tabId){
 const tab=await chrome.tabs.get(tabId);if(!permittedUrl(tab.url))return;
 if(!knownTabs.has(tabId)){knownTabs.add(tabId);await chrome.storage.local.set({privacyKnownTabs:[...knownTabs]});}
 const response=await chrome.tabs.sendMessage(tabId,{type:'REQUEST_CONTEXT'});if(!response?.context)return;
 if(!pageConsent)return;
 const data=await api('/context/update',{...response.context,tab_id:tabId});
 const [active]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
 if(pageConsent&&active?.id===tabId)await api(`/context/activate/${tabId}`,{});return data.context;
}
async function flushResults(){
 const all=await chrome.storage.local.get('resultOutbox');
 for(const[id,entry]of Object.entries(all.resultOutbox||{})){
  try{await api('/actions/result',entry);const latest=(await chrome.storage.local.get('resultOutbox')).resultOutbox||{};delete latest[id];await chrome.storage.local.set({resultOutbox:latest});}catch{}
 }
}
async function runAction(tabId){
 if(!pageConsent)return;
 const tab=await chrome.tabs.get(tabId);if(!permittedUrl(tab.url))return;
 const{action}=await api(`/actions/next?tab_id=${tabId}`);if(!action)return;busy.add(tabId);
 try{
  if(!pageConsent)return;
  await chrome.tabs.sendMessage(tabId,{type:'CONTEXTSWITCH_CV',event:{source:'HAND',action:'TRACKING_LOST'}}).catch(()=>{});
  const marks=(await chrome.storage.local.get('executedActions')).executedActions||{};let result;
  if(marks[action.action_id])result={status:'UNVERIFIED',verified:false,error:'Already attempted; not replayed after restart'};
  else{
   marks[action.action_id]=Date.now();await chrome.storage.local.set({executedActions:Object.fromEntries(Object.entries(marks).slice(-500))});
   if(!pageConsent)return;
   try{result=await chrome.tabs.sendMessage(tabId,{type:'EXECUTE_ACTION',action});}catch(e){result={status:'FAILED',verified:false,error:e.message};}
  }
  if(!pageConsent)return;
  const outbox=(await chrome.storage.local.get('resultOutbox')).resultOutbox||{};
  outbox[action.action_id]={action_id:action.action_id,tab_id:tabId,status:result?.status||'FAILED',verified:result?.verified===true,result:result?.result||{},error:result?.error||null};
  await chrome.storage.local.set({resultOutbox:outbox});await flushResults();
 }finally{busy.delete(tabId);}
}
async function tick(){
 if(!privacyReady||!pageConsent)return;
 if(ticking)return;ticking=true;
 try{
  connect();if(socket?.readyState===WebSocket.OPEN&&Date.now()-lastPing>10000){socket.send('heartbeat');lastPing=Date.now();}
  await flushRevocations();await flushResults();const tabs=await chrome.tabs.query({});
  for(const t of tabs.filter(t=>permittedUrl(t.url))){try{await sync(t.id);await runAction(t.id);}catch{}}
  sendUi({type:'SYSTEM_STATE',state:await api('/system/state')});
 }catch{}finally{ticking=false;}
}
chrome.runtime.onConnect.addListener(port=>{
 if(port.name!=='contextswitch-ui')return;ports.add(port);port.onDisconnect.addListener(()=>ports.delete(port));
 port.onMessage.addListener(async msg=>{
  if(msg.type!=='INTEGRATION_REQUEST')return;
  if(!pageConsent){port.postMessage({type:'INTEGRATION_RESPONSE',id:msg.id,error:'Webpage consent is required before starting ContextSwitch.'});return;}
  if(!['/system/state','/system/camera','/system/head/recenter','/system/camera/preview','/system/modality','/system/context-shift/calibrate','/system/context-shift/stop','/hardware/ports','/hardware/connect','/hardware/calibrate','/commands/preview','/commands/execute','/voice/listen','/voice/devices'].includes(msg.path)&&!/^\/actions\/jobs\/job-[a-f0-9]+$/.test(msg.path))return;
  try{port.postMessage({type:'INTEGRATION_RESPONSE',id:msg.id,data:await api(msg.path,msg.body)});}catch(e){port.postMessage({type:'INTEGRATION_RESPONSE',id:msg.id,error:e.message});}
 });void tick();
});
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
 if(msg?.type==='PRIVACY_GRANT'&&!sender.tab){grantPages(msg.origins||[]).then(data=>{reply(data);void tick();}).catch(e=>reply({error:e.message}));return true;}
 if(msg?.type==='PRIVACY_REVOKE'&&!sender.tab){revokePages().then(reply).catch(e=>reply({error:e.message}));return true;}
 if(!pageConsent)return;
 if(msg?.type==='CONTEXTSWITCH_GET_STATUS'){reply({connected:socket?.readyState===1});return;}
 if(['CONTEXT_UPDATE','START_ACTION_POLLING','INTEGRATION_HEARTBEAT'].includes(msg?.type)){void tick();return;}
 if(msg?.type==='SYNC_ACTIVE_CONTEXT'){
  (async()=>{const[tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});return{context:await sync(tab.id)};})().then(reply).catch(e=>reply({error:e.message}));return true;
 }
});
chrome.tabs.onActivated.addListener(()=>{void cancelAll();void tick();});
chrome.tabs.onUpdated.addListener(()=>void tick());
chrome.tabs.onRemoved.addListener(id=>{if(pageConsent&&knownTabs.has(id))fetch(`${API}/context/remove/${id}`,{method:'DELETE'}).catch(()=>{});knownTabs.delete(id);});
function wake(){chrome.alarms.create('integration-wake',{periodInMinutes:.5});void tick();}
chrome.runtime.onInstalled.addListener(wake);chrome.runtime.onStartup.addListener(wake);chrome.alarms.onAlarm.addListener(()=>void tick());
chrome.permissions.onRemoved.addListener(()=>{if(pageConsent)void revokePages();});
setInterval(()=>void tick(),1200);
void loadPrivacy().then(wake).catch(()=>{privacyReady=true;pageConsent=false;});

