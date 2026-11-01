import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {ExtensionConsent} from './ExtensionConsent';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function browser(approved=false){return{storage:{local:{get:async()=>({})}},permissions:{contains:async()=>approved,request:vi.fn(async()=>approved)},runtime:{sendMessage:vi.fn(async()=>({approved:true}))}};}
it('does not mount live controls until the user and Chrome grant permission',async()=>{
 const chrome=browser(true);vi.stubGlobal('chrome',chrome);
 render(<ExtensionConsent><div>Live controls</div></ExtensionConsent>);
 await screen.findByText('Allow selected sites & start');
 expect(screen.queryByText('Live controls')).toBeNull();
 fireEvent.click(screen.getByText('Allow selected sites & start'));
 await screen.findByText('Live controls');
 expect(chrome.permissions.request).toHaveBeenCalledWith({origins:['https://kicanvas.org/*','https://*.kicanvas.org/*']});
});
it('Chrome denial leaves live controls unmounted',async()=>{
 vi.stubGlobal('chrome',browser(false));
 render(<ExtensionConsent><div>Live controls</div></ExtensionConsent>);
 fireEvent.click(await screen.findByText('Allow selected sites & start'));
 await screen.findByText('Permission was declined. ContextSwitch has not started.');
 expect(screen.queryByText('Live controls')).toBeNull();
});
