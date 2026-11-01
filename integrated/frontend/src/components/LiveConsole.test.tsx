import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {LiveConsole} from './LiveConsole';

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const state={sensors:{CAMERA:{status:'PAUSED'},MICROPHONE:{status:'UNAVAILABLE'},IMU:{status:'UNAVAILABLE'}},active_modality:'HEAD_HAND',recommended_modality:'TYPED',context:{title:'Real schematic',tab_id:7,url:'https://kicanvas.org/'},planner_configured:false};
it('uses real state, previews a command and gates execution on explicit approval',async()=>{
 const requests:{url:string;body:any}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:any)=>{
  const body=options?.body?JSON.parse(options.body):null;requests.push({url,body});
  let data:any=state;
  if(url.endsWith('/commands/preview'))data={preview_id:'p1',transcript:body.text,route:'DETERMINISTIC',plan:{steps:[{action:'search_component'}]},validation:{execution_ready:false}};
  if(url.endsWith('/commands/execute'))data={job:{job_id:'j1',status:'NEEDS_REVIEW',completed_steps:1,total_steps:1,results:[{status:'UNVERIFIED',verified:false}]}};
  return{ok:true,json:async()=>data};
 }));
 render(<LiveConsole/>);await screen.findByText('Real schematic');
 fireEvent.change(screen.getByLabelText('Command'),{target:{value:'find R101'}});
 fireEvent.click(screen.getByText('Preview plan'));
 const execute=await screen.findByText('Execute previewed plan');expect(execute).toBeDisabled();
 fireEvent.click(screen.getByLabelText('I explicitly approve this plan’s confirmation-required actions.'));expect(execute).not.toBeDisabled();fireEvent.click(execute);
 await screen.findByText('Execution: UNVERIFIED — review browser');
 expect(requests.find(r=>r.url.endsWith('/commands/execute'))?.body.approved).toBe(true);
 expect(screen.queryByText('Execution: SUCCESS VERIFIED')).toBeNull();
});
it('disconnected sensors are unknown and commands cannot dispatch',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>{throw Error('offline');}));
 render(<LiveConsole/>);
 await waitFor(()=>expect(screen.getByText('Preview plan')).toBeDisabled());
 expect(screen.getAllByText('UNKNOWN — offline')).toHaveLength(3);
});

it('extension popup exposes compact controls, setup navigation and dashboard link',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>state})));
 const {container}=render(<LiveConsole surface="popup"/>);
 expect(container.querySelector('.cs-popup')).not.toBeNull();
 expect(screen.getByRole('link',{name:'Open full dashboard'})).toHaveAttribute('href','http://127.0.0.1:8001/');
 const setup=screen.getByRole('button',{name:'Setup & calibration'});
 fireEvent.click(setup);
 expect(setup).toHaveAttribute('aria-pressed','true');
 expect(container.querySelector('.cs-popup')).toHaveAttribute('data-popup-tab','setup');
});
