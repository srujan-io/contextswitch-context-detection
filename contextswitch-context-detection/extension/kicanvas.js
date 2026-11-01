// KiCanvas UI adapter. Traverse open shadow roots without running page code.
(() => {
  function queryAll(selector, root = document) {
    const found = [...root.querySelectorAll(selector)];
    if (root.shadowRoot) found.push(...queryAll(selector, root.shadowRoot));
    for (const element of root.querySelectorAll("*")) {
      if (element.shadowRoot) found.push(...queryAll(selector, element.shadowRoot));
    }
    return found;
  }

  function visible(element) {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }

  async function waitFor(read, timeout = 2500) {
    const deadline = Date.now() + timeout;
    do {
      const value = read();
      if (value) return value;
      await new Promise(resolve => setTimeout(resolve, 50));
    } while (Date.now() < deadline);
    return null;
  }

  const normalizeReference = value => String(value || "").replace(/\s+/g, "").toUpperCase();

  async function searchComponent(value) {
    const raw = String(value || "").trim();
    if (!/^[A-Za-z]{1,3}\s*\d+[A-Za-z]?$/.test(raw)) {
      return {status: "FAILED", verified: false, error: "Invalid component reference."};
    }
    const reference = normalizeReference(raw);
    const app = queryAll("kc-schematic-app").find(visible);
    if (!app) return {status: "FAILED", verified: false, error: "Open a loaded KiCanvas schematic with full controls."};

    const panel = queryAll("kc-schematic-symbols-panel", app)[0];
    if (!panel) return {status: "FAILED", verified: false, error: "Symbols panel unavailable. Enable full KiCanvas controls."};
    if (!visible(panel)) {
      const button = queryAll('kc-ui-button[name="symbols"]', app).find(visible);
      if (button) button.click();
    }
    const input = await waitFor(() => queryAll("kc-ui-text-filter-input input", panel).find(visible)
      || queryAll("input", panel).find(visible));
    if (!input) return {status: "FAILED", verified: false, error: "Component search input unavailable."};

    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(input, reference);
    input.dispatchEvent(new Event("input", {bubbles: true, composed: true}));
    input.dispatchEvent(new Event("change", {bubbles: true, composed: true}));
    input.focus();

    const matches = queryAll("kc-ui-menu-item[data-match-text]", panel).filter(item =>
      normalizeReference(item.querySelector("span")?.textContent) === reference);
    if (matches.length !== 1) {
      return {status: "FAILED", verified: false, result: {reference, matches: matches.length},
        error: matches.length ? "Multiple components match on this sheet." : `Component ${reference} not found on the current sheet.`};
    }
    const item = matches[0];
    if (!await waitFor(() => visible(item))) {
      return {status: "FAILED", verified: false, error: "Matching component is hidden by the Symbols filter."};
    }
    item.scrollIntoView({block: "nearest"});
    item.click();
    // KiCanvas enables this control after its viewer emits a selection event.
    const zoom = await waitFor(() => {
      const button = queryAll('kc-ui-button[name="zoom_to_selection"]', app).find(visible);
      return item.hasAttribute("selected") && button && !button.hasAttribute("disabled") ? button : null;
    });
    if (!zoom) return {status: "UNVERIFIED", verified: false, result: {reference}, error: "Component click sent, but viewer selection was not confirmed."};
    zoom.click();
    return {status: "SUCCESS", verified: true, result: {
      reference, selected: true, zoom_to_selection_requested: true,
      verification: "Symbols item selected and viewer zoom-to-selection control enabled."
    }};
  }

  window.BeyondTouchKiCanvas = {searchComponent};
})();
