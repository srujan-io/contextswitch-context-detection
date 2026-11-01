"""One normalized pose producer; never a second gesture pipeline.

Sample is an INTERNAL contract, not a proposed Pico wire protocol. A decoder for
the discovered V1 firmware is decoded by pico_imu.Decoder.
"""
from dataclasses import dataclass
from collections import deque
import importlib
import math
import os
import threading
import time

AXES=('pitch','yaw','roll')
def delta(a,b): return (a-b+180)%360-180


@dataclass(frozen=True)
class Sample:
    device_time: float  # seconds on the hardware clock, normalized by its decoder
    angles: tuple[float,float,float]  # degrees: pitch, yaw, roll
    gyro: tuple[float,float,float]  # degrees/second, same axes
    confidence: float  # decoder reliability score, not a measured probability
    mounted: bool = False


class ClockAlignment:
    def __init__(self): self.reset()
    def reset(self): self.offset=None;self.last=None
    def align(self,device_time,arrival):
        if not math.isfinite(device_time) or not math.isfinite(arrival):raise ValueError('Invalid timestamp')
        if self.last is not None and device_time<=self.last:raise ValueError('Out-of-order/reset device clock; recalibrate')
        candidate=arrival-device_time
        if self.offset is None:self.offset=candidate
        if candidate<self.offset-.05:raise ValueError('Device clock jumped; recalibrate')
        self.offset=min(self.offset,candidate)  # lower-envelope transport delay estimate
        aligned=device_time+self.offset
        self.last=device_time
        if arrival-aligned>.15:raise ValueError('Delayed serial packet')
        return aligned


class PoseFusion:
    def __init__(self,mapping=('pitch','yaw','roll'),clock=time.monotonic):
        if sorted(k.lstrip('-') for k in mapping)!=sorted(AXES):raise ValueError('Mount axes must be a signed permutation of pitch,yaw,roll')
        self.mapping=mapping;self.clock=clock;self.lock=threading.RLock();self.reset()
    def reset(self):
        self.alignment=ClockAlignment();self.latest=None;self.pairs=deque(maxlen=30)
        self.offset=None;self.bias=(0.,0.,0.);self.mode='WEBCAM_ONLY';self.confidence=0.;self.detail='IMU not calibrated';self.last_imu_only=None
    def map_axes(self,values):
        return tuple(values[AXES.index(key.lstrip('-'))]*(-1 if key.startswith('-') else 1) for key in self.mapping)
    def ingest(self,sample,arrival=None):
        arrival=self.clock() if arrival is None else arrival
        with self.lock:
            try:
                if not all(math.isfinite(v) for v in (*sample.angles,*sample.gyro,sample.confidence)) or not 0<=sample.confidence<=1:raise ValueError('Invalid IMU values')
                if max(abs(v) for v in sample.gyro)>600:raise ValueError('Implausible IMU angular velocity')
                aligned=self.alignment.align(sample.device_time,arrival)
                self.latest=(aligned,sample.angles if sample.mounted else self.map_axes(sample.angles),sample.gyro if sample.mounted else self.map_axes(sample.gyro),sample.confidence)
            except Exception as exc:
                self.reset();self.detail=str(exc);return False
        return True
    def disconnect(self):
        with self.lock:self.reset();self.detail='IMU disconnected; calibration cleared'
    def fuse(self,camera,now=None):
        now=self.clock() if now is None else now
        with self.lock:
            camera_time=camera.get('timestamp_monotonic',now) if camera else now
            cv=bool(camera and camera.get('valid_for_actions') and 0<=now-camera_time<=.25 and all(math.isfinite(camera.get(a,float('nan'))) for a in AXES))
            latest=self.latest
            valid=bool(latest and 0<=now-latest[0]<=.25 and latest[3]>=.7)
            if latest and now-latest[0]>.25:
                self.offset=None;self.pairs.clear()  # reconnect requires calibration, not stale offset reuse
            if valid and cv and self.offset is None:
                if not self.pairs or latest[0]!=self.pairs[-1][0]:
                    self.pairs.append((latest[0],tuple(camera[a] for a in AXES),latest[1],latest[2]))
                if len(self.pairs)>=20 and self.pairs[-1][0]-self.pairs[0][0]>=.8:
                    stable=all(max(p[side][i] for p in self.pairs)-min(p[side][i] for p in self.pairs)<3 for side in (1,2) for i in range(3)) and all(abs(v)<5 for p in self.pairs for v in p[3])
                    if stable:
                        self.offset=tuple(sum(delta(p[1][i],p[2][i]) for p in self.pairs)/len(self.pairs) for i in range(3))
                        self.bias=tuple(sum(p[3][i] for p in self.pairs)/len(self.pairs) for i in range(3))
                        self.last_imu_only=now
            imu=valid and self.offset is not None
            target_time=camera_time if cv else now
            corrected=tuple(latest[1][i]+self.offset[i]+(latest[2][i]-self.bias[i])*(target_time-latest[0]) for i in range(3)) if imu else None
            if cv and imu:
                innovation=tuple(delta(camera[a],corrected[i]) for i,a in enumerate(AXES))
                if max(abs(v) for v in innovation)>25:
                    self.offset=None;self.pairs.clear();imu=False;self.detail='IMU/camera disagreement; recalibration required'
                else:
                    # Slow drift correction anchored to the already-filtered webcam.
                    self.offset=tuple(self.offset[i]+.02*innovation[i] for i in range(3))
                    weight=.65*latest[3]
                    pose={a:camera[a]-weight*innovation[i] for i,a in enumerate(AXES)}
                    self.mode='FUSED';self.confidence=min(.99,.7+.25*latest[3]);self.last_imu_only=now
                    return {**camera,**pose,'fusion_mode':self.mode}
            if cv:
                self.mode='WEBCAM_ONLY';self.confidence=.7
                return {**camera,'fusion_mode':self.mode}
            if imu and self.last_imu_only is not None and now-self.last_imu_only<=5:
                # Bound unanchored IMU-only operation: drift cannot run indefinitely.
                self.mode='IMU_ONLY';self.confidence=latest[3]*max(0,1-(now-self.last_imu_only)/6)
                if self.confidence>=.7:return {**dict(zip(AXES,corrected)),'valid_for_actions':True,'tracking_status':'TRACKING','fusion_mode':self.mode}
            self.mode='LOST';self.confidence=0.
            return {'valid_for_actions':False,'tracking_status':'LOST','fusion_mode':'LOST'}
    def snapshot(self):
        return {'mode':self.mode,'confidence':round(self.confidence,3),'confidence_kind':'heuristic reliability',
                'calibrated':self.offset is not None,'detail':self.detail,'sample_age':None if not self.latest else round(self.clock()-self.latest[0],3)}


class SerialIMU:
    def __init__(self,fusion):
        self.fusion=fusion;self.stop=threading.Event();self.thread=None;self.status='UNAVAILABLE'
        self.detail='Configure a serial port to use the discovered Pico IMU V1 firmware';self.port=os.getenv('CONTEXTSWITCH_IMU_PORT','')
        self.decoder=os.getenv('CONTEXTSWITCH_IMU_DECODER','pico_imu:Decoder')
        try:
            self.baud=int(os.getenv('CONTEXTSWITCH_IMU_BAUD','115200'))
            if not 1200<=self.baud<=2000000:raise ValueError('Baud outside allowed range')
        except ValueError:
            self.baud=115200;self.port='';self.detail='Invalid CONTEXTSWITCH_IMU_BAUD; serial input disabled'
        self.calibrate=threading.Event()
    def start(self):
        if not self.port or not self.decoder:return
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        try:
            import serial
            module,name=self.decoder.split(':',1);factory=getattr(importlib.import_module(module),name)
        except Exception as exc:self.detail=f'Decoder/serial unavailable: {exc}';return
        while not self.stop.is_set():
            try:
                with serial.Serial(self.port,self.baud,timeout=.1) as stream:
                    decode=factory()
                    if hasattr(decode,'mount_axes'):decode.mount_axes=self.fusion.mapping
                    stream.reset_input_buffer();self.fusion.disconnect();self.status='RECOVERING'
                    stream.write(b's')  # Actual firmware status command; no calibration assumption.
                    while not self.stop.is_set():
                        if self.calibrate.is_set():
                            self.calibrate.clear();self.fusion.disconnect();decode=factory()
                            if hasattr(decode,'mount_axes'):decode.mount_axes=self.fusion.mapping
                            stream.write(b'c');self.status='RECOVERING'
                        # Firmware-specific framing belongs to the supplied adapter.
                        # No newline, JSON, CSV or binary packet format is assumed.
                        sample=decode(stream)
                        if getattr(decode,'reset_required',False):
                            self.fusion.disconnect();decode.reset_required=False;self.status='RECOVERING'
                        if sample is None:
                            self.detail='Waiting for firmware V1 telemetry / calibration status'
                            if self.fusion.latest and time.monotonic()-self.fusion.latest[0]>.25:self.status='LOST'
                            continue
                        if not isinstance(sample,Sample):raise ValueError('Decoder must return motion.Sample')
                        good=self.fusion.ingest(sample)
                        self.status='TRACKING' if good else 'RECOVERING'
                        self.detail='Serial packets received' if good else self.fusion.detail
            except Exception as exc:
                self.fusion.disconnect();self.status='UNAVAILABLE';self.detail=str(exc);self.stop.wait(1)
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(2)
