
import math
import time


class LowPassFilter:
    def __init__(self):
        self.value = None

    def filter(self, value, alpha):
        if self.value is None:
            self.value = value
        else:
            self.value = alpha * value + (1 - alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


class OneEuroFilter:
    def __init__(self, min_cutoff=1.5, beta=0.08, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        self.signal = LowPassFilter()
        self.derivative = LowPassFilter()

        self.previous_raw = None
        self.previous_time = None

    def alpha(self, cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def update(self, value, timestamp=None):
        if timestamp is None:
            timestamp = time.monotonic()

        if self.previous_time is None:
            self.previous_time = timestamp
            self.previous_raw = value
            return self.signal.filter(value, 1.0)

        dt = max(timestamp - self.previous_time, 0.001)

        dx = (value - self.previous_raw) / dt

        filtered_dx = self.derivative.filter(
            dx,
            self.alpha(self.d_cutoff, dt),
        )

        cutoff = self.min_cutoff + self.beta * abs(filtered_dx)

        result = self.signal.filter(
            value,
            self.alpha(cutoff, dt),
        )

        self.previous_raw = value
        self.previous_time = timestamp

        return result

    def reset(self):
        self.signal.reset()
        self.derivative.reset()
        self.previous_raw = None
        self.previous_time = None


class CursorFilter:
    def __init__(self):
        self.x_filter = OneEuroFilter()
        self.y_filter = OneEuroFilter()

    def update(self, x, y):
        now = time.monotonic()

        x = self.x_filter.update(x, now)
        y = self.y_filter.update(y, now)

        return (
            max(0.0, min(1.0, x)),
            max(0.0, min(1.0, y)),
        )

    def reset(self):
        self.x_filter.reset()
        self.y_filter.reset()
