"""Decoder for the discovered CONTEXTSWITCH_IMU_V1 firmware, unchanged on wire.

CSV: timestamp_ms,ax,ay,az,gx,gy,gz; acceleration g, gyro deg/s.
Firmware commands: c recalibrates (~6 seconds), s requests status.
No magnetometer is streamed: yaw is relative and drifts without webcam anchoring.
"""
import math
import re
from motion import Sample, delta


class Decoder:
    def __init__(self):
        self.buffer=b'';self.ready=False;self.reset_required=False;self.last=None
        self.roll=self.pitch=self.yaw=0.;self.samples=0;self.wrap=0;self.previous_ms=None
        self.mount_axes=('pitch','yaw','roll')
    def __call__(self,stream):
        chunk=stream.read_until(b'\n',size=256)
        self.buffer+=chunk
        if len(self.buffer)>1024:raise ValueError('Oversized IMU frame')
        if b'\n' not in self.buffer:return None
        line,self.buffer=self.buffer.split(b'\n',1)
        return self.parse(line.decode('ascii').strip())
    def parse(self,line):
        if not line:return None
        if line.startswith('#'):
            if 'ERROR_' in line or 'CALIBRATION_FAILED' in line:raise ValueError(line)
            if 'CALIBRATION_START' in line or 'CONTEXTSWITCH_IMU_V1' in line:
                self.ready=False;self.last=None;self.samples=0;self.reset_required=True
            if 'CALIBRATION_DONE' in line:self.ready=True;self.last=None;self.samples=0;self.reset_required=True
            if '# STATUS' in line:
                self.ready=bool(re.search(r'ready=1(?:,|$)',line) and re.search(r'calibrated=1(?:,|$)',line))
                if not self.ready:self.reset_required=True
            return None
        values=line.split(',')
        if len(values)!=7:raise ValueError('Expected firmware V1 seven-column CSV')
        ms=int(values[0]);ax,ay,az,gx,gy,gz=map(float,values[1:])
        if not 0<=ms<=0xffffffff or not all(math.isfinite(v) for v in (ax,ay,az,gx,gy,gz)):raise ValueError('Invalid IMU telemetry')
        if self.previous_ms is not None and ms<self.previous_ms:
            if self.previous_ms>0xf0000000 and ms<0x10000000:self.wrap+=2**32
            else:raise ValueError('Pico restarted; reset clock and calibration')
        self.previous_ms=ms;t=(ms+self.wrap)/1000
        if not self.ready:return None
        magnitude=math.sqrt(ax*ax+ay*ay+az*az)
        if not .5<magnitude<1.5 or max(abs(v) for v in (gx,gy,gz))>250:raise ValueError('Unreliable acceleration/gyro range')
        # Apply the mounting basis to raw gravity and angular velocity BEFORE
        # estimating orientation; swapping Euler angles after a 90° mount is wrong.
        names=('pitch','yaw','roll')
        def mounted(values):return tuple(values[names.index(k.lstrip('-'))]*(-1 if k.startswith('-') else 1) for k in self.mount_axes)
        ay,az,ax=mounted((ay,az,ax));gy,gz,gx=mounted((gy,gz,gx))
        accel_roll=math.degrees(math.atan2(ay,az));accel_pitch=math.degrees(math.atan2(-ax,math.hypot(ay,az)))
        if self.last is None:self.roll=accel_roll;self.pitch=accel_pitch;self.yaw=0.;dt=0.
        else:
            dt=t-self.last
            if not 0<dt<=.2:raise ValueError('Stale/out-of-order firmware sample')
            alpha=math.exp(-dt/.5)
            predicted_roll=self.roll+gx*dt;predicted_pitch=self.pitch+gy*dt
            if abs(magnitude-1)<.15:
                self.roll=predicted_roll+(1-alpha)*delta(accel_roll,predicted_roll)
                self.pitch=predicted_pitch+(1-alpha)*delta(accel_pitch,predicted_pitch)
            else:self.roll=predicted_roll;self.pitch=predicted_pitch
            self.yaw+=gz*dt
        self.last=t;self.samples+=1
        confidence=.9 if abs(magnitude-1)<.15 and self.samples>=10 else .5
        return Sample(t,(self.pitch,self.yaw,self.roll),(gy,gz,gx),confidence,mounted=True)
