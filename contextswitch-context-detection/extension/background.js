importScripts("config.js");
const API = globalThis.BeyondTouchApi;
const contexts = new Map();
const timers = new Map();

async function postContext(tabId, context) {
    try {
        const payload = {
            ...context,
            tab_id: tabId
        };

        const response = await fetch(`${API}/context/update`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(
                `Context update failed: ${response.status} ${errorText}`
            );
        }

        const data = await response.json();

        contexts.set(tabId, data.context);

        await chrome.storage.local.set({
            activeContext: data.context
        });

        console.log("Beyond Touch: Context stored for tab", tabId);

        // Activate only after the context has been stored.
        if (tabId === (await chrome.tabs.query({
            active: true,
            currentWindow: true
        }))[0]?.id) {
            const activation = await fetch(
                `${API}/context/activate/${tabId}`,
                { method: "POST" }
            );

            if (!activation.ok) {
                console.warn(
                    "Context activation failed:",
                    await activation.text()
                );
            }
        }

        return data.context;
    } catch (error) {
        console.error("Beyond Touch context error:", error);
        throw error;
    }
}

async function sendResult(action, result) {
  try {
    await fetch(`${API}/actions/result`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        action_id:action.action_id, tab_id:action.tab_id,
        status:result?.status || "FAILED", verified:result?.verified === true,
        result:result?.result || {}, error:result?.error || null
      })
    });
  } catch (e) { console.warn("Result upload failed:", e.message); }
}

async function poll(tabId) {
  try {
    const r = await fetch(`${API}/actions/next?tab_id=${tabId}`);
    if (!r.ok) return;
    const data = await r.json();
    if (!data.action) return;
    let result;
    try {
      result = await chrome.tabs.sendMessage(tabId, {
        type:"EXECUTE_ACTION", action:data.action
      });
    } catch (e) {
      result = {status:"FAILED", verified:false, error:`Content script unavailable: ${e.message}`};
    }
    await sendResult(data.action, result);
  } catch (_) { /* Backend may be offline; retry on next interval. */ }
}

function startPolling(tabId) {
  if (timers.has(tabId)) return;
  poll(tabId);
  timers.set(tabId, setInterval(() => poll(tabId), 1200));
}
function stopPolling(tabId) {
  if (timers.has(tabId)) clearInterval(timers.get(tabId));
  timers.delete(tabId);
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "SYNC_ACTIVE_CONTEXT") {
    (async () => {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (!tab?.id || !/^https?:/.test(tab.url || "")) throw new Error("Open a KiCanvas schematic tab first.");
      let response;
      try {
        response = await chrome.tabs.sendMessage(tab.id, {type: "REQUEST_CONTEXT"});
      } catch (_) {
        throw new Error("Refresh the KiCanvas tab after reloading the extension, then reopen this popup.");
      }
      if (!response?.context) throw new Error("Refresh the KiCanvas tab to load the updated content script.");
      const context = await postContext(tab.id, response.context);
      startPolling(tab.id);
      return {context};
    })().then(sendResponse).catch(error => sendResponse({error: error.message}));
    return true;
  }
  if (msg?.type === "CONTEXT_UPDATE" && sender.tab?.id != null) {
    postContext(sender.tab.id, msg.context)
      .then(context => sendResponse({context}))
      .catch(error => sendResponse({error: error.message}));
    return true;
  }
  if (msg?.type === "START_ACTION_POLLING" && sender.tab?.id != null)
    startPolling(sender.tab.id);
});

async function refresh(tabId) {
  console.log("MY KICANVAS TAB ID:", tabId);
    try {
        const tab = await chrome.tabs.get(tabId);

        if (!/^https?:/.test(tab.url || "")) {
            return;
        }

        startPolling(tabId);

        // Ask content.js to collect and send fresh context.
        // postContext() will activate the tab after storage.
        await chrome.tabs.sendMessage(tabId, {
            type: "REQUEST_CONTEXT"
        }).catch(error => {
            console.warn(
                "Could not request context from tab:",
                error.message
            );
        });

    } catch (error) {
        console.warn("Tab refresh error:", error.message);
    }
}

chrome.tabs.onActivated.addListener(({tabId}) => refresh(tabId));
chrome.tabs.onUpdated.addListener((id, info, tab) => {
  if (info.status === "complete" && tab.active) refresh(id);
});
chrome.tabs.onRemoved.addListener(async id => {
  stopPolling(id); contexts.delete(id);
  try { await fetch(`${API}/context/remove/${id}`, {method:"DELETE"}); } catch (_) {}
});
chrome.runtime.onInstalled.addListener(async () => {
  const tabs = await chrome.tabs.query({});
  tabs.forEach(t => { if (t.id != null && /^https?:/.test(t.url || "")) startPolling(t.id); });
});
