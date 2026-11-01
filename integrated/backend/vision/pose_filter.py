"""Angle-safe eye-line roll and adaptive One Euro filtering."""
import math


def matrix_pose(matrix):
    """Euler angles from MediaPipe's canonical-face rotation, ignoring translation/scale."""
    r=[[float(matrix[i][j]) for j in range(3)] for i in range(3)]
    for j in range(3):
        scale=math.sqrt(sum(r[i][j]**2 for i in range(3)))
        if scale<1e-6: raise ValueError('Invalid face transform')
        for i in range(3):r[i][j]/=scale
    return {'pitch':math.degrees(math.atan2(r[2][1],r[2][2])),
            'yaw':math.degrees(math.atan2(-r[2][0],math.hypot(r[0][0],r[1][0]))),
            'roll':math.degrees(math.atan2(r[1][0],r[0][0]))}


def eye_roll(dx, dy):
    # Eye landmarks can point right-to-left; the eye line is unoriented.
    # Treat +179/-179 as -1/+1, not a full-turn gesture.
    return (math.degrees(math.atan2(dy, dx)) + 90) % 180 - 90


class OneEuro:
    def __init__(self, min_cutoff=1.2, beta=.035):
        self.min_cutoff, self.beta = min_cutoff, beta
        self.value = self.raw = self.timestamp = None
        self.derivative = 0.

    @staticmethod
    def alpha(cutoff, dt):
        return 1 / (1 + 1 / (2 * math.pi * cutoff * dt))

    def update(self, value, now):
        if self.timestamp is None or now-self.timestamp > .5:
            self.value = self.raw = value
            self.timestamp = now
            self.derivative = 0.
            return value
        dt = max(.001, now-self.timestamp)
        derivative = (value-self.raw)/dt
        a = self.alpha(1.,dt)
        self.derivative += a*(derivative-self.derivative)
        a = self.alpha(self.min_cutoff+self.beta*abs(self.derivative),dt)
        self.value += a*(value-self.value)
        self.raw, self.timestamp = value, now
        return self.value
