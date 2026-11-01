(() => {
  if (window.__beyondTouchInstalled) return;
  window.__beyondTouchInstalled = true;
  const clean = (v, n=180) => (v || "").replace(/\s+/g," ").trim().slice(0,n);

  function pageType() {
    const h=location.hostname.toLowerCase(), p=location.pathname.toLowerCase();
    if (h==="kicanvas.org" || h.endsWith(".kicanvas.org")) return "schematic_viewer";
    if (h==="youtube.com" || h.endsWith(".youtube.com") || h==="youtu.be") {
      if(p==="/") return "homepage";
      if(p==="/watch" || h==="youtu.be") return "video_player";
      if(p==="/results") return "search_results";
      if(p.startsWith("/playlist")) return "playlist";
      if(p.startsWith("/shorts/")) return "shorts";
      if(p.startsWith("/@") || p.startsWith("/channel/") || p.startsWith("/c/")) return "channel_page";
      return "other";
    }
    return "unknown";
  }
  function websiteId() {
    const h=location.hostname.toLowerCase();
    if(h==="kicanvas.org" || h.endsWith(".kicanvas.org")) return "kicanvas";
    if(h==="youtube.com" || h.endsWith(".youtube.com") || h==="youtu.be") return "youtube";
    return "unknown";
  }
  function selectedElement() {
    const selection=window.getSelection()?.toString().trim();
    const el=document.activeElement;
    const chosen=document.querySelector('[aria-selected="true"],[aria-pressed="true"],[data-selected="true"],.selected,.is-selected');
    if(selection) return {type:"text",text:clean(selection,300)};
    if(chosen) return {type:"element",tag:chosen.tagName.toLowerCase(),role:chosen.getAttribute("role"),label:clean(chosen.getAttribute("aria-label")||chosen.innerText||chosen.textContent)};
    if(el && el!==document.body && el!==document.documentElement)
      return {type:"focused_element",tag:el.tagName.toLowerCase(),role:el.getAttribute("role"),label:clean(el.getAttribute("aria-label")||el.getAttribute("placeholder")||el.innerText||el.textContent)};
    return null;
  }
  function relevantElements() {
    const selectors=["h1","h2","video","button","[role='button']","input","[role='search']","a[title]","[aria-label]","ytd-video-primary-info-renderer","ytd-watch-metadata","ytd-video-renderer","ytd-rich-item-renderer"];
    const out=[], seen=new Set();
    for(const s of selectors) for(const el of document.querySelectorAll(s)) {
      if(out.length>=35) break;
      const r=el.getBoundingClientRect(), st=getComputedStyle(el);
      if(!r.width||!r.height||st.visibility==="hidden"||st.display==="none") continue;
      const label=clean(el.getAttribute("aria-label")||el.getAttribute("title")||el.getAttribute("placeholder")||el.innerText||el.textContent,120);
      if(!label && el.tagName!=="VIDEO") continue;
      const key=el.tagName+":"+label; if(seen.has(key)) continue; seen.add(key);
      out.push({tag:el.tagName.toLowerCase(),role:el.getAttribute("role"),label});
    }
    return out;
  }
  function collectContext(reason) {
    const v=document.querySelector("video"), h=location.hostname.toLowerCase();
    return {
      url:location.href, hostname:h, title:clean(document.title,200),
      website_id:websiteId(), page_type:pageType(), project:null,
      selected_component:selectedElement(), available_elements:relevantElements(),
      page_summary:clean(document.querySelector("main")?.innerText||document.body?.innerText,500),
      media:v?{present:true,paused:v.paused,current_time_seconds:Math.round(v.currentTime||0),duration_seconds:Number.isFinite(v.duration)?Math.round(v.duration):null}:{present:false},
      event_reason:reason, captured_at:new Date().toISOString()
    };
  }
  let updateTimer;
  function sendUpdate(reason) {
    clearTimeout(updateTimer);
    updateTimer=setTimeout(()=>chrome.runtime.sendMessage({
      type:"CONTEXT_UPDATE",context:collectContext(reason)
    }).catch(()=>{}),250);
  }

  // Module E: allowlisted KiCanvas action handlers.
  function visible(el) {
    if(!el) return false;
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.display!=="none" && s.visibility!=="hidden";
  }
  function schematicSurface() {
    for(const selector of ["canvas","svg","[role='application']","[class*='canvas']","[class*='schematic']","kicanvas"]) {
      const found=[...document.querySelectorAll(selector)].find(visible);
      if(found) return found;
    }
    return null;
  }
  function searchInput() {
    return [...document.querySelectorAll("input:not([type='hidden']),[role='searchbox']")]
      .filter(visible).find(el=>/search|component|reference|designator/i.test(
        `${el.placeholder||""} ${el.getAttribute("aria-label")||""} ${el.name||""}`)) || null;
  }
  function setValue(input,value) {
    const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input),"value")?.set;
    if(setter) setter.call(input,value); else input.value=value;
    input.dispatchEvent(new Event("input",{bubbles:true}));
    input.dispatchEvent(new Event("change",{bubbles:true}));
  }
  async function execute(action) {
    if(websiteId()!=="kicanvas" || pageType()!=="schematic_viewer")
      return {status:"FAILED",verified:false,error:"This action executor currently supports KiCanvas schematic pages only."};
    const p=action.parameters||{}, name=action.action;
    if(name==="zoom_in" || name==="zoom_out") {
      const el=schematicSurface();
      if(!el) return {status:"FAILED",verified:false,error:"No visible schematic surface found."};
      const r=el.getBoundingClientRect();
      el.dispatchEvent(new WheelEvent("wheel",{bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2,deltaY:name==="zoom_in"?-120:120}));
      return {status:"UNVERIFIED",verified:false,result:{wheel_event_dispatched:true},error:"Event sent; actual zoom change needs KiCanvas-specific verification."};
    }
    if(name==="pan") {
      if(!["up","down","left","right"].includes(p.direction))
        return {status:"FAILED",verified:false,error:"Invalid pan direction."};
      const el=schematicSurface();
      if(!el) return {status:"FAILED",verified:false,error:"No visible schematic surface found."};
      const d={up:[0,-160],down:[0,160],left:[-160,0],right:[160,0]}[p.direction],r=el.getBoundingClientRect();
      el.dispatchEvent(new WheelEvent("wheel",{bubbles:true,cancelable:true,view:window,clientX:r.left+r.width/2,clientY:r.top+r.height/2,deltaX:d[0],deltaY:d[1]}));
      return {status:"UNVERIFIED",verified:false,result:{wheel_event_dispatched:true,direction:p.direction},error:"Event sent; actual pan needs KiCanvas-specific verification."};
    }
    if(name==="search_component") {
      const result = await window.BeyondTouchKiCanvas.searchComponent(p.query);
      sendUpdate("component_search");
      return result;
    }
    if(name==="view_component_details") {
      const ref=String(p.reference||"").trim();
      if(!/^[A-Za-z]{1,3}\s*\d+[A-Za-z]?$/.test(ref))
        return {status:"FAILED",verified:false,error:"Invalid component reference."};
      const selected=document.querySelector('[aria-selected="true"],[data-selected="true"],.selected,.is-selected');
      const label=selected?clean(selected.getAttribute("aria-label")||selected.textContent,120):"";
      if(!selected || !label.toLowerCase().includes(ref.toLowerCase()))
        return {status:"UNVERIFIED",verified:false,result:{reference:ref,selected_label:label},error:"Requested component is not verifiably selected."};
      selected.dispatchEvent(new MouseEvent("dblclick",{bubbles:true,cancelable:true}));
      return {status:"UNVERIFIED",verified:false,result:{reference:ref,double_click_dispatched:true},error:"Double-click sent; details panel visibility is not verified."};
    }
    return {status:"FAILED",verified:false,error:`Unsupported action: ${name}`};
  }

  chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
    if(message?.type==="REQUEST_CONTEXT") {
      sendResponse({context:collectContext("context_requested")});
      return;
    }
    if(message?.type==="EXECUTE_ACTION") {
      execute(message.action).then(sendResponse).catch(e=>sendResponse({status:"FAILED",verified:false,error:e.message||"Execution error"}));
      return true;
    }
  });
  document.addEventListener("selectionchange",()=>sendUpdate("selection_change"));
  document.addEventListener("focusin",()=>sendUpdate("focus_change"));
  document.addEventListener("click",()=>sendUpdate("click"));
  document.addEventListener("change",()=>sendUpdate("input_change"));
  let lastUrl=location.href;
  setInterval(()=>{if(location.href!==lastUrl){lastUrl=location.href;sendUpdate("url_change");}},1000);
  sendUpdate("initial_load");
  chrome.runtime.sendMessage({type:"START_ACTION_POLLING"}).catch(()=>{});
})();
