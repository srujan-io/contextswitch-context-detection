setInterval(()=>chrome.runtime.sendMessage({type:'INTEGRATION_HEARTBEAT'}).catch(()=>{}),2000);
