# Beyond Touch - Context Detection MVP

## What this starter implements
- Browser extension observes the active webpage.
- Detects KiCanvas and YouTube from hostname and URL path.
- Collects a limited DOM summary and current text/element selection.
- Sends context to FastAPI.
- Backend maintains per-tab context and loads the matching skill pack.

## 1. Start the backend
From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Open http://127.0.0.1:8001/docs and check `/health`.
The context backend uses port 8001 because the separate ContextSwitch CV service uses 8000.

## 2. Load the extension
1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Choose Load unpacked.
4. Select the `extension` folder.
5. Open or refresh a KiCanvas or YouTube tab.

For the debugging popup, add this to the `action` section of `extension/manifest.json`:
`"default_popup": "popup.html"`.

## 3. Inspect results
- Backend API docs: http://127.0.0.1:8001/docs
- Active context: http://127.0.0.1:8001/context/active
- Health: http://127.0.0.1:8001/health

## 4. Test component search in KiCanvas
1. Start the context backend on port 8001.
2. Reload the unpacked extension, then refresh the KiCanvas tab to load its updated scripts.
3. Open your schematic with full viewer controls enabled.
4. Open the extension popup. It requests fresh context from this tab and stores it in the backend.
5. Enter an existing reference (for example, `C101` in `Embedded_v1.kicad_sch`) and click **Find in KiCanvas**.
6. The queued action opens Symbols, filters the current sheet, clicks the exact reference, and requests zoom to selection.

The popup reports the job result. Selection is verified using the selected Symbols entry and enabled viewer zoom control; the zoom request itself is not a measurement of camera movement. Missing or ambiguous references fail without selecting a different component. Search currently covers the active sheet only.

Run adapter regression checks with `node --test extension/tests/kicanvas.test.cjs`.

## Important limitations
- DOM extraction is intentionally limited; it does not send the full page HTML.
- Generic selection detection reports highlighted text, selected/pressed elements, or the focused element. Website-specific selected-component detection may need KiCanvas DOM inspection.
- YouTube is a single-page application. The content script watches URL changes, but YouTube DOM selectors may change over time.
- This is a local hackathon prototype. Restrict CORS, extension host permissions, data collection and API access before production.
- The in-memory state is for a single backend process and is lost when it restarts.
- Page text is untrusted data, never instructions to the agent.
