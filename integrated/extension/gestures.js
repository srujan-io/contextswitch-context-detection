
(() => {
  if (window.__CONTEXTSWITCH_INSTALLED__) return;
  window.__CONTEXTSWITCH_INSTALLED__ = true;

  console.log("[ContextSwitch] Content script loaded");

  // ============================================
  // CONFIGURATION
  // ============================================

  const CONFIG = {
    cursorSize: 20,
    panStep: 180,
    zoomStep: 180,
    cursorSmoothing: 0.35,
    mirrorX: false,
    clickTolerance: 35
  };

  // ============================================
  // STATE
  // ============================================

  let cursorX = window.innerWidth / 2;
  let cursorY = window.innerHeight / 2;

  let cursorVisible = false;
  let pinching = false;

  let pointerDownTarget = null;
  let pointerDownX = 0;
  let pointerDownY = 0;

  let feedbackTimeout = null;
  let zoomActive = false;
  let lastGesture = Date.now();
  setInterval(() => { if(Date.now()-lastGesture>1000) {trackingLost();zoomActive=false;} },250);

  // ============================================
  // UTILITIES
  // ============================================

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function getTarget(x = cursorX, y = cursorY) {
    let target = document.elementFromPoint(x, y);
    for(let depth=0;depth<20;depth++) {
      const inner = target?.shadowRoot?.elementFromPoint?.(x,y);
      if(!inner || inner===target) break;
      target=inner;
    }
    return target;
  }

  function dispatchPointer(
    target,
    type,
    buttons = 0
  ) {
    if (!target) return;

    const isDown = type === "pointerdown";

    target.dispatchEvent(
      new PointerEvent(type, {
        bubbles: true,
        cancelable: true,
        composed: true,
        pointerId: 42,
        pointerType: "mouse",
        isPrimary: true,
        clientX: cursorX,
        clientY: cursorY,
        button: isDown ? 0 : -1,
        buttons
      })
    );
  }

  function dispatchMouse(
    target,
    type,
    buttons = 0
  ) {
    if (!target) return;

    target.dispatchEvent(
      new MouseEvent(type, {
        bubbles: true,
        cancelable: true,
        composed: true,
        clientX: cursorX,
        clientY: cursorY,
        button: 0,
        buttons
      })
    );
  }

  // ============================================
  // VIRTUAL CURSOR
  // ============================================

  const cursor = document.createElement("div");
  cursor.id = "contextswitch-cursor";

  Object.assign(cursor.style, {
    position: "fixed",
    left: `${cursorX}px`,
    top: `${cursorY}px`,
    width: `${CONFIG.cursorSize}px`,
    height: `${CONFIG.cursorSize}px`,
    background: "#00e5ff",
    border: "2px solid white",
    borderRadius: "50%",
    boxShadow: "0 0 15px rgba(0,229,255,0.8)",
    transform: "translate(-50%, -50%)",
    pointerEvents: "none",
    zIndex: "2147483647",
    display: "none"
  });

  document.documentElement.appendChild(cursor);

  function setCursorPinchStyle(active) {
    cursor.style.background = active
      ? "#ff3b81"
      : "#00e5ff";

    cursor.style.boxShadow = active
      ? "0 0 18px rgba(255,59,129,0.9)"
      : "0 0 15px rgba(0,229,255,0.8)";
  }

  function moveCursor(parameters = {}) {
    let x = Number(parameters.x);
    let y = Number(parameters.y);

    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return;
    }

    x = clamp(x, 0, 1);
    y = clamp(y, 0, 1);

    if (CONFIG.mirrorX) {
      x = 1 - x;
    }

    const targetX = x * window.innerWidth;
    const targetY = y * window.innerHeight;

    if (!cursorVisible) {
      cursorX = targetX;
      cursorY = targetY;
    } else {
      cursorX += (
        targetX - cursorX
      ) * CONFIG.cursorSmoothing;

      cursorY += (
        targetY - cursorY
      ) * CONFIG.cursorSmoothing;
    }

    cursor.style.left = `${cursorX}px`;
    cursor.style.top = `${cursorY}px`;
    cursor.style.display = "block";

    cursorVisible = true;

    const target = getTarget();

    if (target) {
      dispatchPointer(
        target,
        "pointermove",
        pinching ? 1 : 0
      );

      dispatchMouse(
        target,
        "mousemove",
        pinching ? 1 : 0
      );
    }
  }

  // ============================================
  // PINCH START
  // ============================================

  function pinchStart() {
    console.log("[ContextSwitch] PINCH_START received");

    if (pinching || !cursorVisible) return;

    pinching = true;
    setCursorPinchStyle(true);

    pointerDownTarget = getTarget();
    pointerDownX = cursorX;
    pointerDownY = cursorY;

    if (pointerDownTarget) {
      console.log(
        "[ContextSwitch] Pinch target:",
        pointerDownTarget
      );

      dispatchPointer(
        pointerDownTarget,
        "pointerdown",
        1
      );

      dispatchMouse(
        pointerDownTarget,
        "mousedown",
        1
      );
    }

    showFeedback("PINCH START");
  }

  // ============================================
  // PINCH END / CLICK
  // ============================================

  function pinchEnd() {
    console.log("[ContextSwitch] PINCH_END received");

    if (!pinching) return;

    pinching = false;
    setCursorPinchStyle(false);

    const releaseTarget = getTarget();

    const distance = Math.hypot(
      cursorX - pointerDownX,
      cursorY - pointerDownY
    );

    const target =
      releaseTarget || pointerDownTarget;

    if (target) {
      dispatchPointer(
        target,
        "pointerup",
        0
      );

      dispatchMouse(
        target,
        "mouseup",
        0
      );
    }

    if (distance <= CONFIG.clickTolerance && target) {
      const clickable = target.closest?.(
        [
          "button",
          "a",
          "input",
          "label",
          "select",
          "summary",
          "[role='button']",
          "[role='menuitem']",
          "[tabindex]"
        ].join(",")
      );

      const clickTarget = clickable || target;

      const sameTarget =
        target === pointerDownTarget ||
        clickTarget === pointerDownTarget ||
        clickTarget.contains?.(pointerDownTarget) ||
        pointerDownTarget?.contains?.(target);

      if (sameTarget) {
        console.log(
          "[ContextSwitch] Clicking:",
          clickTarget
        );

        if (
          typeof clickTarget.click === "function" &&
          clickTarget instanceof HTMLElement
        ) {
          clickTarget.click();
        } else {
          dispatchMouse(
            clickTarget,
            "click",
            0
          );
        }

        showFeedback("CLICK");
      } else {
        console.log(
          "[ContextSwitch] Click cancelled: target changed",
          { pointerDownTarget, releaseTarget }
        );

        showFeedback("CLICK CANCELLED");
      }
    } else {
      console.log(
        "[ContextSwitch] Pinch released without click",
        { distance }
      );

      showFeedback("PINCH END");
    }

    pointerDownTarget = null;
  }

  // ============================================
  // TRACKING LOST
  // ============================================

  function trackingLost() {
    if (pinching) {
      // Release any held pointer, but do not click
      // when tracking is lost.
      const target = getTarget() || pointerDownTarget;

      if (target) {
        dispatchPointer(target, "pointerup", 0);
        dispatchMouse(target, "mouseup", 0);
      }
    }

    pinching = false;
    pointerDownTarget = null;
    cursorVisible = false;

    cursor.style.display = "none";
    setCursorPinchStyle(false);
  }

  // ============================================
  // HEAD GESTURES
  // ============================================

  function getViewerTarget() {
    return (
      window.BeyondTouchKiCanvas?.surface?.() ||
      document.querySelector("kicanvas-embed") ||
      document.querySelector("canvas") ||
      document.querySelector("kicanvas-app") ||
      document.body
    );
  }

  function dispatchWheel(
    deltaX,
    deltaY,
    ctrlKey = false
  ) {
    const viewer = getViewerTarget();
    const rect = viewer.getBoundingClientRect();

    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;

    const target = viewer;

    target.dispatchEvent(
      new WheelEvent("wheel", {
        bubbles: true,
        cancelable: true,
        composed: true,
        clientX: x,
        clientY: y,
        deltaX,
        deltaY,
        deltaMode: 0,
        ctrlKey
      })
    );

    console.log(
      "[ContextSwitch] Wheel dispatched",
      { deltaX, deltaY, ctrlKey }
    );
  }

  function executeHeadAction(action) {
    switch (action) {
      case "HEAD_UP":
        dispatchWheel(0, -CONFIG.panStep);
        break;

      case "HEAD_DOWN":
        dispatchWheel(0, CONFIG.panStep);
        break;

      case "HEAD_LEFT":
        dispatchWheel(-CONFIG.panStep, 0);
        break;

      case "HEAD_RIGHT":
        dispatchWheel(CONFIG.panStep, 0);
        break;

      case "HEAD_TILT_LEFT":
        dispatchWheel(0, CONFIG.zoomStep, true);
        break;

      case "HEAD_TILT_RIGHT":
        dispatchWheel(0, -CONFIG.zoomStep, true);
        break;

      default:
        return;
    }

    showFeedback(action);

    console.log(
      "[ContextSwitch] Head action:",
      action
    );
  }

  // ============================================
  // FEEDBACK OVERLAY
  // ============================================

  const overlay = document.createElement("div");
  overlay.id = "contextswitch-feedback";

  Object.assign(overlay.style, {
    position: "fixed",
    top: "20px",
    right: "20px",
    zIndex: "2147483647",
    padding: "12px 18px",
    background: "#111827",
    color: "#ffffff",
    border: "1px solid #4b5563",
    borderRadius: "10px",
    fontFamily: "Arial, sans-serif",
    fontSize: "14px",
    fontWeight: "bold",
    pointerEvents: "none",
    display: "none"
  });

  document.documentElement.appendChild(overlay);

  function showFeedback(text) {
    overlay.textContent = `ContextSwitch: ${text}`;
    overlay.style.display = "block";

    clearTimeout(feedbackTimeout);

    feedbackTimeout = setTimeout(() => {
      overlay.style.display = "none";
    }, 1000);
  }

  // ============================================
  // CONNECTION INDICATOR
  // ============================================

  const statusBadge = document.createElement("div");
  statusBadge.id = "contextswitch-status";

  Object.assign(statusBadge.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "2147483647",
    padding: "8px 12px",
    borderRadius: "8px",
    background: "#7f1d1d",
    color: "white",
    fontFamily: "Arial, sans-serif",
    fontSize: "12px",
    pointerEvents: "none"
  });

  statusBadge.textContent = "ContextSwitch: Disconnected";
  document.documentElement.appendChild(statusBadge);

  function updateStatus(connected) {
    statusBadge.textContent = connected
      ? "ContextSwitch: Connected"
      : "ContextSwitch: Disconnected";

    statusBadge.style.background = connected
      ? "#14532d"
      : "#7f1d1d";
  }

  // ============================================
  // EVENT ROUTING
  // ============================================

  chrome.runtime.onMessage.addListener((message) => {
    if(message.type==='PRIVACY_REVOKED'){trackingLost();zoomActive=false;statusBadge.style.display='none';return;}
    if(message.type==='PRIVACY_GRANTED'){statusBadge.style.display='block';return;}
    if(globalThis.__CONTEXTSWITCH_PAGE_ALLOWED__===false)return;
    if (message.type === "CONTEXTSWITCH_STATUS") {
      updateStatus(Boolean(message.connected));
      if(!message.connected) {trackingLost();zoomActive=false;}
      return;
    }

    if (message.type !== "CONTEXTSWITCH_CV") {
      return;
    }

    const event = message.event;

    if (!event?.action) return;
    lastGesture=Date.now();

    if (event.source === "HAND") {
      switch (event.action) {
        case "SCROLL":
          if(!zoomActive && Number.isFinite(event.parameters?.delta_y)) {trackingLost();dispatchWheel(0,event.parameters.delta_y);}
          break;
        case "CURSOR_MOVE":
          moveCursor(event.parameters);
          break;

        case "PINCH_START":
          if(!zoomActive) pinchStart();
          break;

        case "PINCH_END":
          if(!zoomActive) pinchEnd();
          break;

        case "PINCH_CANCEL":
          trackingLost();
          break;
        case "PINCH_ZOOM_START":
          trackingLost();zoomActive=true;
          break;
        case "PINCH_ZOOM":
          if(zoomActive && Number.isFinite(event.parameters?.delta)) dispatchWheel(0,-event.parameters.delta*180,true);
          break;
        case "PINCH_ZOOM_END":
          trackingLost();zoomActive=false;
          break;

        case "TRACKING_LOST":
          trackingLost();
          zoomActive=false;
          break;
      }

      return;
    }

    if (event.source === "HEAD") {
      if(!zoomActive) executeHeadAction(event.action);
    }
  });

  // ============================================
  // INITIAL CONNECTION STATUS
  // ============================================

  chrome.runtime.sendMessage(
    { type: "CONTEXTSWITCH_GET_STATUS" },
    (response) => {
      if (chrome.runtime.lastError) return;

      updateStatus(Boolean(response?.connected));
    }
  );

  console.log(
    "[ContextSwitch] Ready: cursor, pinch, head gestures"
  );
})();
