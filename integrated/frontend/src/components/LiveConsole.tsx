import { useEffect, useRef, useState } from 'react';
import { LiveView } from './LiveView';

export type State = {sensors:Record<string,{status:string;timestamp:number}>;active_modality:string;recommended_modality:string;camera_detail:string;context:Record<string,unknown>;planner_configured:boolean;build?:string;browser_connected?:boolean;head?:{state:string;calibrated:boolean;delta:Record<string,number>;thresholds?:Record<string,number>;calibration_progress?:number};camera_performance?:{processing_fps:number;processing_ms:number};voice_capture?:{phase:string;level_hint?:string;duration_seconds?:number;rms?:number};context_shift?:{enabled:boolean;calibrating:boolean;assessment_complete?:boolean;seconds_remaining:number;mode:string;reason:string;audio_samples:number;visual_samples:number;audio_error?:string;instruction?:string;baseline_rms?:number|null;peak_rms?:number|null;peak_amplitude?:number|null;speech_to_noise_ratio?:number|null;hands?:{hand_count:number;fully_visible_count:number;both_hands_visible:boolean;two_hands_possibly_occupied:boolean;incomplete_frame:boolean}|null};fusion?:{mode:string;confidence:number;calibrated:boolean;detail:string};imu?:{status:string;detail:string}};
export type Preview = {preview_id:string;transcript:string;route:string;plan:{needs_clarification?:boolean;clarification_question?:string;steps:unknown[]};validation?:{requires_confirmation?:boolean;execution_ready?:boolean;confirmation_required?:boolean}};
export type Job = {job_id:string;status:string;completed_steps:number;total_steps:number;results:unknown[]};
type Port = {postMessage:(v:unknown)=>void;disconnect:()=>void;onMessage:{addListener:(f:(m:any)=>void)=>void};onDisconnect:{addListener:(f:()=>void)=>void}};

/** Live controls are separate from the preserved, explicitly isolated simulation. */
export function LiveConsole({surface='dashboard'}:{surface?:'dashboard'|'popup'}={}) {
 const [state,setState]=useState<State|null>(null),[text,setText]=useState(''),[preview,setPreview]=useState<Preview|null>(null);
 const [job,setJob]=useState<Job|null>(null),[error,setError]=useState(''),[connected,setConnected]=useState(false),[working,setWorking]=useState(false),[approved,setApproved]=useState(false);
 const [devices,setDevices]=useState<{index:number;name:string;host_api:string;default:boolean}[]>([]),[device,setDevice]=useState(''),[language,setLanguage]=useState('en-US'),[listening,setListening]=useState(false),[audioHint,setAudioHint]=useState('');
 const [preContext,setPreContext]=useState(''),[handsBusy,setHandsBusy]=useState(false);
 const [showPreview,setShowPreview]=useState(false),[cameraPreview,setCameraPreview]=useState<string|null>(null);
 const [hardwarePorts,setHardwarePorts]=useState<{port:string;description:string}[]>([]),[imuPort,setImuPort]=useState(''),[imuAxes,setImuAxes]=useState('pitch,yaw,roll');
 const port=useRef<Port|null>(null),pending=useRef(new Map<string,{resolve:(v:any)=>void;reject:(e:Error)=>void}>()),isExtension=useRef(false);
 async function request(path:string,body?:unknown):Promise<any> {
  if(port.current) return new Promise((resolve,reject)=>{
   const id=crypto.randomUUID();pending.current.set(id,{resolve,reject});
   port.current!.postMessage({type:'INTEGRATION_REQUEST',id,path,body});
   setTimeout(()=>{if(pending.current.delete(id))reject(Error('Backend request timed out'));},27000);
  });
  if(isExtension.current) throw Error('Extension worker reconnecting');
  const r=await fetch('http://127.0.0.1:8001'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?null:JSON.stringify(body),signal:AbortSignal.timeout(27000)});
  const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
 }
 useEffect(()=>{
  if(!showPreview||!connected){setCameraPreview(null);return;}
  let disposed=false;
  const poll=()=>void request('/system/camera/preview').then(r=>{if(!disposed)setCameraPreview(r.image?`data:image/jpeg;base64,${r.image}`:null);}).catch(()=>{});
  poll();const timer=setInterval(poll,500);
  return()=>{disposed=true;clearInterval(timer);};
 },[showPreview,connected]);
 useEffect(()=>{
  if(!connected)return;
  void request('/voice/devices').then(r=>setDevices(r.devices??[])).catch(()=>{});
  void request('/hardware/ports').then(r=>setHardwarePorts(r.ports??[])).catch(()=>{});
 },[connected]);
 useEffect(()=>{
  if(!listening)return;
  const timer=setInterval(()=>request('/system/state').then(setState).catch(()=>{}),200);
  return()=>clearInterval(timer);
 },[listening]);
 useEffect(()=>{
  let disposed=false;
  let retry:ReturnType<typeof setTimeout>|undefined;
  const chrome=(globalThis as unknown as {chrome?:{runtime?:{id?:string;connect:(v:{name:string})=>Port}}}).chrome;
  isExtension.current=!!chrome?.runtime?.id;
  function attach(){
   if(disposed || !chrome?.runtime?.id)return;
   port.current=chrome.runtime.connect({name:'contextswitch-ui'});
   port.current.onMessage.addListener(m=>{
    if(m.type==='INTEGRATION_RESPONSE') {const p=pending.current.get(m.id);pending.current.delete(m.id);if(m.error)p?.reject(Error(m.error));else p?.resolve(m.data);}
    if(m.type==='SYSTEM_STATE'){setState(m.state);setConnected(true);}
   });
   port.current.onDisconnect.addListener(()=>{
    port.current=null;
    if(disposed)return;
    setConnected(false);
    for(const p of pending.current.values())p.reject(Error('Worker disconnected; preview again before retrying'));
    pending.current.clear();
    retry=setTimeout(attach,1000);
   });
  }
  attach();
  const poll=async()=>{try{const s=await request('/system/state');if(!disposed){setState(s);setConnected(true);}}catch{if(!disposed)setConnected(false);}};
  void poll();const timer=setInterval(poll,2000);
  return()=>{disposed=true;clearInterval(timer);clearTimeout(retry);port.current?.disconnect();port.current=null;};
 },[]);
 useEffect(()=>{
  if(!job||!['QUEUED','RUNNING'].includes(job.status))return;
  const timer=setInterval(()=>request('/actions/jobs/'+job.job_id).then(setJob).catch(e=>setError(e.message)),1000);
  return()=>clearInterval(timer);
 },[job?.job_id,job?.status]);
 async function act(fn:()=>Promise<void>){setWorking(true);setError('');try{await fn();}catch(e){setError((e as Error).message);}finally{setWorking(false);}}
 const previewCommand=()=>void act(async()=>{setPreview(null);setJob(null);setApproved(false);setPreview(await request('/commands/preview',{text,source:'TYPED'}));});
 const refreshDevices=()=>void act(async()=>{const r=await request('/voice/devices');setDevices(r.devices??[]);if(r.error)setError(r.error);});
 const record=()=>void act(async()=>{
  setPreview(null);setJob(null);setApproved(false);setAudioHint('');setListening(true);
  try{
   const r=await request('/voice/listen',{device_index:device===''?null:Number(device),language,seconds:5});
   if(r.voice_event?.text)setText(r.voice_event.text);
   if(r.audio_diagnostics)setAudioHint(`${r.audio_diagnostics.level_hint} · ${r.audio_diagnostics.duration_seconds}s · RMS ${r.audio_diagnostics.rms}`);
   if(r.result?.preview_id)setPreview(r.result);
   if(r.result?.job)setJob(r.result.job);
   if(!r.result?.preview_id&&!r.result?.job)setError([r.error??r.result?.message??'No transcript returned.',r.error_detail].filter(Boolean).join(' — '));
  }finally{setListening(false);}
 });
 return <LiveView m={{state,preview,job,connected,working,listening,text,error,audioHint,devices,device,language,approved,
  surface,
  showPreview,cameraPreview,togglePreview:()=>setShowPreview(v=>!v),
  preContext,setPreContext,handsBusy,setHandsBusy,
  hardwarePorts,imuPort,setImuPort,imuAxes,setImuAxes,
  connectImu:()=>void act(async()=>setState(await request('/hardware/connect',{port:imuPort,baud:115200,axes:imuAxes.split(',').map(s=>s.trim())}))),
  calibrateImu:()=>void act(async()=>{await request('/hardware/calibrate',{});setState(await request('/system/state'));}),
  calibrate:()=>void act(async()=>{await request('/system/context-shift/calibrate',{pre_context:preContext,hands_occupied:handsBusy,device_index:device===''?null:Number(device)});setState(await request('/system/state'));}),
  stopAuto:()=>void act(async()=>{await request('/system/context-shift/stop',{});setState(await request('/system/state'));}),
  setText:value=>{setText(value);setPreview(null);setApproved(false);},setDevice,setLanguage,setApproved,previewCommand,record,refreshDevices,
  camera:()=>void act(async()=>setState(await request('/system/camera',{paused:!['PAUSED','UNAVAILABLE'].includes(state?.sensors['CAMERA']?.status??'PAUSED')}))),
  recenter:()=>void act(async()=>{await request('/system/head/recenter',{});setState(await request('/system/state'));}),
  execute:()=>void act(async()=>setJob((await request('/commands/execute',{preview_id:preview?.preview_id,approved})).job)),
  mode:modality=>void act(async()=>setState(await request('/system/modality',{modality}))),
 }}/>;
}



