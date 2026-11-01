import { useEffect, useState, type ReactNode } from 'react';
import { ArrowUpRight, ShieldCheck } from 'lucide-react';
const KEY='contextswitch.pageConsent.v1';
const KICANVAS=['https://kicanvas.org/*','https://*.kicanvas.org/*'];
const YOUTUBE=['https://*.youtube.com/*'];
type Browser={storage:{local:{get:(key:string)=>Promise<Record<string,any>>}};permissions:{contains:(value:{origins:string[]})=>Promise<boolean>;request:(value:{origins:string[]})=>Promise<boolean>};runtime:{sendMessage:(message:unknown)=>Promise<any>}};
export function ExtensionConsent({children}:{children:ReactNode}) {
 const [status,setStatus]=useState<'loading'|'pending'|'approved'>('loading'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [kicanvas,setKicanvas]=useState(true),[youtube,setYoutube]=useState(false);
 const browser=(globalThis as unknown as {chrome?:Browser}).chrome;
 useEffect(()=>{let disposed=false;(async()=>{
  if(!browser){setStatus('pending');return;}
  const saved=(await browser.storage.local.get(KEY))[KEY];
  const allowed=!!saved?.approved&&saved.origins?.length>0&&await browser.permissions.contains({origins:saved.origins});
  if(!disposed)setStatus(allowed?'approved':'pending');
 })().catch(()=>{if(!disposed)setStatus('pending');});return()=>{disposed=true;};},[]);
 async function allow(){
  if(!browser){setError('Open ContextSwitch from the Chrome extension icon.');return;}
  const origins=[...(kicanvas?KICANVAS:[]),...(youtube?YOUTUBE:[])];
  setBusy(true);setError('');
  try{
   // Call Chrome directly in the click handler, preserving the user gesture.
   if(!await browser.permissions.request({origins})){setError('Permission was declined. ContextSwitch has not started.');return;}
   const result=await browser.runtime.sendMessage({type:'PRIVACY_GRANT',origins});
   if(result?.error)throw Error(result.error);
   setStatus('approved');
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 async function revoke(){
  setBusy(true);
  setStatus('pending');
  try{await browser?.runtime.sendMessage({type:'PRIVACY_REVOKE'});setStatus('pending');}
  catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 if(status==='approved')return <>{children}<div className="cs-permission-footer"><ShieldCheck size={13}/><span>Website access is enabled for your selected sites.</span><button disabled={busy} onClick={()=>void revoke()}>Revoke access</button></div></>;
 return <main className="cs-consent"><img src="../icons/icon-128.png" alt=""/><div className="cs-eyebrow">YOU’RE IN CONTROL</div><h1>Welcome to<br/>ContextSwitch<span>.</span></h1><p>Choose whether ContextSwitch may access your supported webpages before it starts.</p><div className="cs-consent-box"><ShieldCheck size={21}/><div><b>What you’re allowing</b><ul><li>Read the page URL, title, focused controls and relevant visible text.</li><li>Send that context to your local backend and execute your validated browser commands.</li><li>Contextual planning may send page context to Gemini when configured.</li></ul></div></div><fieldset disabled={busy||status==='loading'}><legend>ALLOW ACCESS TO</legend><label><input type="checkbox" checked={kicanvas} onChange={e=>setKicanvas(e.target.checked)}/>KiCanvas</label><label><input type="checkbox" checked={youtube} onChange={e=>setYoutube(e.target.checked)}/>YouTube</label></fieldset><p className="cs-consent-note">Camera and microphone use are separate choices. Calibration samples local audio levels; spoken-command audio is sent to Google Web Speech. No webpage scripts run before your approval.</p>{error&&<p role="alert">{error}</p>}<button className="cs-button primary" disabled={busy||status==='loading'||(!kicanvas&&!youtube)} onClick={()=>void allow()}>{status==='loading'?'Checking permission…':'Allow selected sites & start'}<ArrowUpRight size={15}/></button><button className="cs-button" disabled={busy} onClick={()=>setError('Not started. You can allow access here whenever you’re ready.')}>Not now</button></main>;
}
