async function showContext() {
  const status = document.getElementById("status");
  const output = document.getElementById("context");
  try {
    const context = await syncContext();
    status.textContent = "Active tab context received";
    output.textContent = JSON.stringify(context, null, 2);
  } catch (error) {
    status.textContent = error.message;
    output.textContent = `Context backend: ${globalThis.BeyondTouchApi}. Make sure it is running, then reopen the popup.`;
  }
}
async function syncContext() {
  const response = await chrome.runtime.sendMessage({type: "SYNC_ACTIVE_CONTEXT"});
  if (response?.error) throw new Error(response.error);
  if (!response?.context) throw new Error("No context response. Reload the extension and refresh KiCanvas.");
  return response.context;
}
showContext();

// This explicit click approves one deterministic search through the normal queue.
document.getElementById("search-form").addEventListener("submit", async event => {
  event.preventDefault();
  const output = document.getElementById("search-result");
  const button = document.getElementById("search-button");
  button.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id) throw new Error("No active tab.");
    const api = globalThis.BeyondTouchApi;
    async function request(path, options) {
      const response = await fetch(api + path, options);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      return data;
    }
    const context = await syncContext();
    if (context.tab_id !== tab.id) throw new Error("Active tab changed. Reopen the popup on your schematic.");
    if (context.website_id !== "kicanvas" || context.page_type !== "schematic_viewer") {
      throw new Error("Open and refresh a KiCanvas schematic tab first.");
    }
    const query = document.getElementById("reference").value.trim();
    const queued = await request("/actions/dispatch", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({tab_id: tab.id, context, user_approved: true,
        plan: {website: "kicanvas", intent: `Find ${query}`, steps: [
          {action: "search_component", parameters: {query}, target: "component_search"}
        ]}})
    });
    output.textContent = `Queued ${queued.job.job_id}. Waiting for extension…`;
    for (let attempt = 0; attempt < 30; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 500));
      const job = await request(`/actions/jobs/${queued.job.job_id}`);
      if (["COMPLETED", "FAILED", "NEEDS_REVIEW"].includes(job.status)) {
        output.textContent = JSON.stringify(job, null, 2);
        return;
      }
    }
    output.textContent = `Still waiting: ${queued.job.job_id}. Keep the schematic tab open and check backend job status.`;
  } catch (error) {
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
