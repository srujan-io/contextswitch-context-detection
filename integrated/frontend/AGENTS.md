<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## ContextSwitch architecture
- The popup UI (`src/components/PopupView`) only talks to the extension background worker via `services/contextSwitchBridge` (chrome.runtime Port); never open a WebSocket from the UI — the background worker owns the backend connection.
- Demo mode runs `services/simulationEngine` in isolation and must never route through the bridge; simulated values/commands are tagged "simulated", never "executed"/"measured".
- Backend message names are mapped in `EVENT_TYPE_MAP`/`EventAdapter`; adapt there instead of changing UI event types.
