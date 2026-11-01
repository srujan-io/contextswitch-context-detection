from threading import RLock


class ContextStore:
    """In-memory per-tab context store for a single-process local demo."""

    def __init__(self):
        self._contexts = {}
        self._active_tab_id = None
        self._lock = RLock()

    def update(self, tab_id: int, context: dict):
        with self._lock:
            self._contexts[tab_id] = context
            self._active_tab_id = tab_id

    def set_active(self, tab_id: int):
        with self._lock:
            if tab_id in self._contexts:
                self._active_tab_id = tab_id

    def get(self, tab_id: int):
        with self._lock:
            return self._contexts.get(tab_id, {"message": "No context for this tab yet."})

    def get_active(self):
        with self._lock:
            if self._active_tab_id is None:
                return {"message": "No active context yet."}
            return self._contexts.get(self._active_tab_id, {"message": "No active context yet."})

    def remove(self, tab_id: int):
        with self._lock:
            self._contexts.pop(tab_id, None)
            if self._active_tab_id == tab_id:
                self._active_tab_id = next(iter(self._contexts), None)
