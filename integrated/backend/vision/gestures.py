
import time
import math
from collections import deque
from statistics import median


class GestureRecognizer:
    def __init__(self):
        self.neutral = None

        self.calibration_samples = deque(maxlen=20)
        self.samples = deque(maxlen=5)

        self.thresholds = {
            "pitch": 10.0,
            "yaw": 12.0,
            "roll": 12.0,
        }

        self.release_ratio = 0.65
        self.hold_seconds = 0.18
        self.cooldown_seconds = 0.7
        self.state = "NEUTRAL"
        self.last_delta = {}
        self.release_since = None
        self.calibration_since = None
        self.calibration_min_samples = 8
        self.calibration_seconds = 1.2

        self.candidate = None
        self.candidate_since = 0.0
        self.last_emit = 0.0
        self.armed = True

    def _angles(self, pose):
        if not isinstance(pose, dict):
            return None

        if not pose.get("valid_for_actions", False):
            return None

        try:
            angles = {
                axis: float(pose[axis])
                for axis in ("pitch", "yaw", "roll")
            }
            return angles if all(math.isfinite(v) for v in angles.values()) else None
        except (KeyError, ValueError, TypeError):
            return None

    def calibrate(self, pose):
        angles = self._angles(pose)

        if angles is None:
            return False

        self.neutral = angles.copy()
        self.calibration_samples.clear()
        self.samples.clear()
        self.candidate = None
        self.armed = True

        print(
            "[HEAD] Manual calibration:",
            self.neutral,
            flush=True,
        )

        return True

    def reset(self):
        self.neutral = None
        self.calibration_samples.clear()
        self.samples.clear()
        self.candidate = None
        self.armed = True
        self.release_since = None
        self.state = "CALIBRATING"
        self.last_delta = {}
        self.calibration_since = None

    def auto_calibrate(self, pose):
        now = time.monotonic()
        angles = self._angles(pose)

        if angles is None:
            self.calibration_samples.clear()
            self.calibration_since = None
            return False

        if self.calibration_since is None:self.calibration_since=now
        self.calibration_samples.append(angles)

        if len(self.calibration_samples) < self.calibration_min_samples:
            return False

        neutral = {}

        for axis in ("pitch", "yaw", "roll"):
            values = [
                sample[axis]
                for sample in self.calibration_samples
            ]

            if max(values) - min(values) > 6.0:
                self.calibration_samples.clear()
                self.calibration_since = None
                return False

            neutral[axis] = median(values)

        if now-self.calibration_since < self.calibration_seconds:return False

        self.neutral = neutral
        self.samples.clear()
        self.calibration_samples.clear()
        self.candidate = None
        self.armed = True

        print(
            "[HEAD] Auto calibration successful:",
            self.neutral,
            flush=True,
        )

        return True

    def process(self, pose):
        now = time.monotonic()

        angles = self._angles(pose)

        if angles is None:
            self.candidate = None
            self.samples.clear()
            self.calibration_samples.clear()
            self.calibration_since = None
            self.armed = False
            self.release_since = None
            self.state = "TRACKING_LOST"
            return None

        if self.neutral is None:
            self.auto_calibrate(pose)
            self.state = "NEUTRAL" if self.neutral else "CALIBRATING"
            return None

        self.samples.append(angles)

        delta = {}

        for axis in ("pitch", "yaw", "roll"):
            values = [
                sample[axis]
                for sample in self.samples
            ]

            delta[axis] = (
                median(values) - self.neutral[axis]
            )
        delta["roll"] = (delta["roll"]+90)%180-90
        self.last_delta = {axis:round(value,2) for axis,value in delta.items()}

        # Choose the strongest threshold-normalized axis.
        axis = max(
            delta,
            key=lambda a: (
                abs(delta[a]) / self.thresholds[a]
            ),
        )

        magnitude = abs(delta[axis])
        threshold = self.thresholds[axis]

        if all(
            abs(delta[a])
            < self.thresholds[a] * self.release_ratio
            for a in delta
        ):
            if self.release_since is None: self.release_since = now
            if now-self.release_since >= .18: self.armed = True
            self.candidate = None
            self.state = "NEUTRAL" if self.armed else "WAITING_FOR_RELEASE"
            return None

        self.release_since = None

        if not self.armed or magnitude < threshold:
            self.candidate = None
            self.state = "WAITING_FOR_RELEASE" if not self.armed else "NEUTRAL"
            return None

        strengths = sorted((abs(delta[a])/self.thresholds[a] for a in delta),reverse=True)
        if strengths[1] > .8 and strengths[0] < strengths[1]*1.25:
            self.candidate = None
            self.state = "NEUTRAL"
            return None

        mapping = {
            ("pitch", 1): "SCROLL_DOWN",
            ("pitch", -1): "SCROLL_UP",
            ("yaw", 1): "NEXT_PAGE",
            ("yaw", -1): "PREVIOUS_PAGE",
            ("roll", 1): "ZOOM_IN",
            ("roll", -1): "ZOOM_OUT",
        }

        sign = 1 if delta[axis] > 0 else -1
        action = mapping[(axis, sign)]

        if action != self.candidate:
            self.candidate = action
            self.candidate_since = now
            self.state = "CANDIDATE"
            return None

        if now - self.candidate_since < self.hold_seconds:
            return None

        if now - self.last_emit < self.cooldown_seconds:
            return None

        self.last_emit = now
        self.armed = False
        self.candidate = None
        self.state = "FIRED"

        print(
            f"[HEAD GESTURE] {action} "
            f"delta={delta[axis]:.2f}",
            flush=True,
        )

        return {
            "action": action,
            "parameters": {
                "axis": axis,
                "magnitude": round(delta[axis], 2),
            },
        }
