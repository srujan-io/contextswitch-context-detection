"""Palm-normalized extension of the existing pinch-click contract.

Short stable pinch remains a click. Hold 350ms then change aperture to zoom;
cancel the pending click before any zoom. Loss always cancels, never clicks.
"""
import time


class PinchZoom:
    def __init__(self):
        self.state = "IDLE"
        self.since = 0
        self.base = None

    def process(self, hand, now=None):
        now = time.monotonic() if now is None else now
        if not hand or not hand.get("detected"):
            events = ["PINCH_CANCEL", "PINCH_ZOOM_END"] if self.state != "IDLE" else []
            self.state, self.base = "IDLE", None
            return [(name,{}) for name in events]
        ratio = hand.get("pinch_ratio")
        if ratio is None:
            return []
        if self.state == "IDLE" and hand.get("pinching"):
            self.state, self.since, self.base = "ARMING", now, ratio
        elif self.state == "ARMING":
            if not hand.get("pinching"):
                self.state = "IDLE"
            elif now-self.since >= .35 and abs(ratio-self.base) > .08:
                self.state, self.base = "ACTIVE", ratio
                return [("PINCH_CANCEL",{}),("PINCH_ZOOM_START",{})]
        elif self.state == "ACTIVE":
            if ratio > .8:
                self.state, self.since = "RELEASING", now
                return [("PINCH_ZOOM_END",{})]
            delta = max(-1,min(1,(ratio-self.base)*3))
            self.base = ratio
            if abs(delta) > .015:
                return [("PINCH_ZOOM", {"delta": delta})]
        elif self.state == "RELEASING" and now-self.since >= .15:
            self.state = "IDLE"
        return []
