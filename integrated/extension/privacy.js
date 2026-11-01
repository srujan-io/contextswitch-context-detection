/* Consent is checked before any page context read, injection or execution. */
const PRIVACY_KEY='contextswitch.pageConsent.v1';
const SITE_ORIGINS=['https://kicanvas.org/*','https://*.kicanvas.org/*','https://*.youtube.com/*'];
let pageConsent=false,grantedOrigins=[],privacyReady=false;
const knownTabs=new Set();
function permittedUrl(url){
 if(!pageConsent)return false;
 try{const u=new URL(url);return grantedOrigins.some(pattern=>{const host=new URL(pattern.replace('*.', 'wildcard.')).hostname;return pattern.includes('*.')?(u.hostname===host.replace('wildcard.','')||u.hostname.endsWith('.'+host.replace('wildcard.',''))):u.hostname===host;})&&u.protocol==='https:';}catch{return false;}
}
async function registerPages(){
 await chrome.scripting.unregisterContentScripts({ids:['contextswitch-pages']}).catch(()=>{});
 if(!pageConsent)return;
 await chrome.scripting.registerContentScripts([{id:'contextswitch-pages',matches:grantedOrigins,js:['kicanvas.js','content.js','gestures.js','heartbeat.js'],runAt:'document_idle',persistAcrossSessions:false}]);
}
async function loadPrivacy(){
 for(const id of (await chrome.storage.local.get('privacyKnownTabs')).privacyKnownTabs||[])knownTabs.add(id);
 const saved=(await chrome.storage.local.get(PRIVACY_KEY))[PRIVACY_KEY];
 grantedOrigins=(saved?.origins||[]).filter(p=>SITE_ORIGINS.includes(p));
 pageConsent=!!saved?.approved&&grantedOrigins.length>0&&await chrome.permissions.contains({origins:grantedOrigins});
 if(!pageConsent)grantedOrigins=[];
 await registerPages();privacyReady=true;
}
async function injectPage(tab){
 if(!permittedUrl(tab.url))return;
 await chrome.scripting.executeScript({target:{tabId:tab.id},files:['kicanvas.js','content.js','gestures.js','heartbeat.js']});
 await chrome.tabs.sendMessage(tab.id,{type:'PRIVACY_GRANTED'}).catch(()=>{});
 knownTabs.add(tab.id);
 await chrome.storage.local.set({privacyKnownTabs:[...knownTabs]});
}
async function grantPages(origins){
 privacyReady=false;
 const selected=origins.filter(p=>SITE_ORIGINS.includes(p));
 if(!selected.length||!await chrome.permissions.contains({origins:selected}))throw Error('Chrome has not granted the selected website permissions.');
 grantedOrigins=selected;pageConsent=true;
 await chrome.storage.local.set({[PRIVACY_KEY]:{approved:true,origins:selected,grantedAt:Date.now()}});
 await registerPages();
 const tabs=await chrome.tabs.query({});
 const pending=(await chrome.storage.local.get('privacyRevocations')).privacyRevocations||[];
 await chrome.storage.local.set({privacyRevocations:[...new Set([...pending,...tabs.filter(t=>permittedUrl(t.url)).map(t=>t.id)])]});
 for(const tab of tabs.filter(t=>permittedUrl(t.url)))await injectPage(tab).catch(()=>{});
 privacyReady=true;
 return {approved:true,origins:selected};
}
async function revokePages(){
 const targets=[...knownTabs];const previous=grantedOrigins;
 pageConsent=false;grantedOrigins=[];
 const pending=(await chrome.storage.local.get('privacyRevocations')).privacyRevocations||[];
 await chrome.storage.local.set({[PRIVACY_KEY]:{approved:false,origins:[]},privacyRevocations:[...new Set([...pending,...targets])],privacyKnownTabs:[],resultOutbox:{}});
 if(socket){socket.close();socket=null;}
 await registerPages();
 await Promise.allSettled(targets.map(id=>chrome.tabs.sendMessage(id,{type:'PRIVACY_REVOKED'})));
 try{await api('/system/browser/revoke',{tab_ids:targets});await chrome.storage.local.set({privacyRevocations:[]});}catch{}
 await chrome.permissions.remove({origins:previous}).catch(()=>{});
 knownTabs.clear();
 sendUi({type:'CONNECTION_STATUS',status:'disconnected'});
 return {approved:false,origins:[]};
}
async function flushRevocations(){
 const saved=await chrome.storage.local.get('privacyRevocations');
 if(saved.privacyRevocations?.length){await api('/system/browser/revoke',{tab_ids:saved.privacyRevocations});await chrome.storage.local.set({privacyRevocations:[]});}
}
