function showError(detail: string): void {
  const panel = document.getElementById("popup-diagnostic");
  if (!panel) return;
  panel.hidden = false;
  panel.textContent = `ContextSwitch popup could not start.\n\n${detail}\n\nReload the extension at chrome://extensions.`;
}

window.addEventListener(
  "error",
  (event) => showError(event.message || "Popup script failed to load."),
  true,
);
window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  showError(reason instanceof Error ? reason.message : String(reason ?? "Unexpected async error."));
});

window.addEventListener("load", () => {
  window.setTimeout(() => {
    if (!document.getElementById("root")?.hasChildNodes()) {
      showError("The popup loaded but the UI did not render.");
    }
  }, 2000);
});
