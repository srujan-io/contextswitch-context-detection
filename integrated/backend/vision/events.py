
import time

from vision.cursor_filter import CursorFilter


HEAD_ACTIONS = {
    "SCROLL_UP": "HEAD_UP",
    "SCROLL_DOWN": "HEAD_DOWN",
    "PREVIOUS_PAGE": "HEAD_LEFT",
    "NEXT_PAGE": "HEAD_RIGHT",
    "ZOOM_OUT": "HEAD_TILT_LEFT",
    "ZOOM_IN": "HEAD_TILT_RIGHT",
}


class EventTranslator:
    def __init__(self, cursor_hz=30, pinch_debounce_ms=60):
        self.cursor_interval = 1.0 / cursor_hz
        self.last_cursor_time = 0.0

        self.cursor_filter = CursorFilter()

        self.last_hand_detected = False
        self.last_head_valid = False
        self.last_pinching = False

        self.pinch_debounce = pinch_debounce_ms / 1000.0
        self.pinch_candidate = None
        self.pinch_candidate_since = None

    def make_event(self, source, action, parameters=None):
        return {
            "source": source,
            "action": action,
            "parameters": parameters or {},
            "timestamp": int(time.time() * 1000),
        }

    def process_head(self, pose, gesture_event=None):
        events = []

        valid = bool(
            pose and pose.get("valid_for_actions",True)
        )

        if not valid:
            if self.last_head_valid:
                events.append(
                    self.make_event("HEAD", "TRACKING_LOST")
                )

            self.last_head_valid = False
            return events

        self.last_head_valid = True

        if gesture_event:
            old_action = gesture_event.get("action")
            action = HEAD_ACTIONS.get(old_action)

            if action:
                events.append(
                    self.make_event(
                        "HEAD",
                        action,
                        gesture_event.get("parameters", {}),
                    )
                )

        return events

    def process_hand(self, hand):
        events = []
        now = time.monotonic()

        detected = bool(
            hand and hand.get("detected")
        )

        if not detected:
            if self.last_hand_detected:
                if self.last_pinching:
                    events.append(
                        self.make_event("HAND", "PINCH_END")
                    )

                events.append(
                    self.make_event("HAND", "TRACKING_LOST")
                )

            self.last_hand_detected = False
            self.last_pinching = False
            self.pinch_candidate = None
            self.pinch_candidate_since = None
            self.cursor_filter.reset()

            return events

        self.last_hand_detected = True

        x = hand.get("index_x")
        y = hand.get("index_y")

        if x is not None and y is not None:
            x, y = self.cursor_filter.update(
                float(x), float(y)
            )

            if now - self.last_cursor_time >= self.cursor_interval:
                events.append(
                    self.make_event(
                        "HAND",
                        "CURSOR_MOVE",
                        {
                            "x": round(x, 4),
                            "y": round(y, 4),
                        },
                    )
                )

                self.last_cursor_time = now

        raw_pinching = bool(hand.get("pinching"))

        if raw_pinching == self.last_pinching:
            self.pinch_candidate = None
            self.pinch_candidate_since = None

        else:
            if self.pinch_candidate != raw_pinching:
                self.pinch_candidate = raw_pinching
                self.pinch_candidate_since = now

            elif (
                now - self.pinch_candidate_since
                >= self.pinch_debounce
            ):
                self.last_pinching = raw_pinching

                action = (
                    "PINCH_START"
                    if raw_pinching
                    else "PINCH_END"
                )

                events.append(
                    self.make_event("HAND", action)
                )

                self.pinch_candidate = None
                self.pinch_candidate_since = None

        return events
