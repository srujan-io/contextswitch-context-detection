import asyncio
import os
import threading
import time
import base64
from pathlib import Path
from motion import PoseFusion, SerialIMU


class CameraRuntime:
    def __init__(self, publish, arbiter):
        self.publish, self.arbiter = publish, arbiter
        self.stop = threading.Event()
        self.paused = not (os.getenv("BEYOND_TOUCH_CAMERA", "0") == "1")
        self.thread = None
        self.detail = "Camera paused; enable explicitly"
        self.recenter = threading.Event()
        self.recenter_at=0.
        self.head_state = {"state":"PAUSED","calibrated":False,"delta":{}}
        mounting_error=None
        try:self.fusion=PoseFusion(tuple(s.strip() for s in os.getenv('CONTEXTSWITCH_IMU_AXES','pitch,yaw,roll').split(',')))
        except ValueError as exc:self.fusion=PoseFusion();mounting_error=str(exc)
        self.imu=SerialIMU(self.fusion)
        if mounting_error:self.imu.port='';self.imu.detail=mounting_error
        self.context_shift=None
        self.retry_camera=threading.Event()
        self.last_imu_status=None;self.last_imu_heartbeat=0.
        self.preview=None;self.preview_time=0.;self.performance={}

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def status(self, value, detail=None):
        self.arbiter.status("CAMERA", value)
        if detail is not None:
            self.detail = detail
        self.publish({"type":"SENSOR_STATUS", "sensor":"CAMERA", "status":value,
                      "timestamp":int(time.time()*1000), "detail":self.detail})

    def cancel(self):
        for source in ("HAND", "HEAD"):
            self.publish({"source":source,"action":"TRACKING_LOST","parameters":{},"timestamp":int(time.time()*1000)})

    def run(self):
        from vision.gestures import GestureRecognizer
        from vision.events import EventTranslator
        self.gestures=GestureRecognizer();self.translator=EventTranslator(cursor_hz=25)
        self.run_camera()
        # A camera driver/model failure must not stop a calibrated serial source.
        while not self.stop.is_set():
            if self.retry_camera.is_set():
                self.retry_camera.clear();self.run_camera()
            elif not self.paused:
                for event in self.head_events(None):self.publish(event)
                if self.context_shift:self.context_shift.observe_visual(self.arbiter.head_valid,False)
            else:self.arbiter.head_valid=False
            self.stop.wait(.02)

    def head_events(self,pose):
        if self.recenter.is_set():
            if time.monotonic()<self.recenter_at:
                self.arbiter.head_valid=False
                return []
            self.gestures.reset();self.fusion.disconnect();self.recenter.clear();self.cancel()
        fused=self.fusion.fuse(pose)
        self.arbiter.head_valid=bool(fused.get('valid_for_actions'))
        self.arbiter.status('IMU',self.imu.status)
        now=time.monotonic()
        if self.imu.status!=self.last_imu_status or now-self.last_imu_heartbeat>1.5:
            self.publish({'type':'SENSOR_STATUS','sensor':'IMU','status':self.imu.status,
                          'timestamp':int(time.time()*1000),'detail':self.imu.detail})
            self.last_imu_status=self.imu.status;self.last_imu_heartbeat=now
        gesture=self.gestures.process(fused)
        self.head_state={'state':self.gestures.state,'calibrated':self.gestures.neutral is not None,
                         'delta':self.gestures.last_delta,'thresholds':self.gestures.thresholds,
                         'tracking':fused.get('tracking_status'),'fusion':self.fusion.snapshot()}
        g=self.gestures
        elapsed=0 if g.calibration_since is None else now-g.calibration_since
        self.head_state['calibration_progress']=1. if g.neutral else round(min(1.,len(g.calibration_samples)/g.calibration_min_samples,elapsed/g.calibration_seconds),2)
        return self.translator.process_head(fused,gesture)

    def run_camera(self):
        cap = head = hand = None
        last_status = "UNAVAILABLE"
        last_heartbeat = 0
        try:
            while not self.stop.is_set():
                if self.paused:
                    self.arbiter.hand_valid=False
                    self.preview=None
                    self.arbiter.head_valid=False
                    if last_status!='PAUSED':self.fusion.disconnect()
                    self.head_state = {"state":"PAUSED","calibrated":False,"delta":{}}
                    if cap:
                        cap.release(); cap = None
                    if head:
                        head.close(); head = None
                    if hand:
                        hand.close(); hand = None
                    self.cancel() if last_status != "PAUSED" else None
                    last_status = "PAUSED"
                    if time.monotonic()-last_heartbeat > 1.5:
                        self.status("PAUSED"); last_heartbeat = time.monotonic()
                    self.stop.wait(.05)
                    continue
                if cap is None:
                    import cv2
                    from vision.head_tracker import HeadTracker
                    from vision.hand_tracker import HandTracker
                    from vision.gestures import GestureRecognizer
                    from vision.events import EventTranslator
                    from vision.pinch_zoom import PinchZoom
                    from vision.hand_scroll import HandScroll
                    cap = cv2.VideoCapture(int(os.getenv("BEYOND_TOUCH_CAMERA_INDEX","0")), cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        raise RuntimeError("Camera could not be opened")
                    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                    cap.set(cv2.CAP_PROP_FPS,30)
                    models = Path(__file__).parent/"models"
                    head = HeadTracker(str(models/"face_landmarker.task"))
                    hand = HandTracker(str(models/"hand_landmarker.task"))
                    gestures, translator, zoom = self.gestures, self.translator, PinchZoom()
                    gestures.reset()
                    scroll = HandScroll()
                    self.detail = "Camera opened; hold neutral for calibration"
                ok, frame = cap.read()
                captured_at=time.monotonic()
                if not ok:
                    self.cancel(); self.status("TEMPORARILY_LOST", "Frame read failed")
                    for event in self.head_events(None):self.publish(event)
                    self.stop.wait(.1)
                    continue
                frame = cv2.flip(frame,1)
                if frame.shape[1]>640:
                    frame=cv2.resize(frame,(640,round(frame.shape[0]*640/frame.shape[1])))
                pose = head.process(frame)
                pose['timestamp_monotonic']=captured_at
                hand_data = hand.process(frame)
                hand_valid=bool(hand_data.get('detected')) and (not self.context_shift or not self.context_shift.enabled or (hand_data.get('both_hands_visible',False) and hand_data.get('control_ready',False) and not hand_data.get('two_hands_possibly_occupied',False)))
                if self.arbiter.hand_valid and not hand_valid:self.publish(translator.make_event('HAND','TRACKING_LOST'))
                self.arbiter.hand_valid=hand_valid
                if hand_data.get('control_hand_changed'):
                    for event in translator.process_hand(None):
                        if event['action']!='PINCH_END':self.publish(event)
                    zoom.process(None);scroll.process(None,time.monotonic())
                state = "TRACKING" if pose.get("valid_for_actions") or hand_data.get("detected") else pose.get("tracking_status","LOST")
                if state != last_status or time.monotonic()-last_heartbeat > 1.5:
                    self.status(state); last_status, last_heartbeat = state, time.monotonic()
                events=self.head_events(pose)
                duration=time.monotonic()-captured_at
                self.performance={'processing_ms':round(duration*1000),'processing_fps':round(1/max(.001,duration),1),
                                  'width':frame.shape[1],'height':frame.shape[0]}
                if time.monotonic()-self.preview_time>.25:
                    color=(100,235,160) if self.head_state['state']=='NEUTRAL' else (80,160,240)
                    cv2.putText(frame,f"Head: {self.head_state['state']}",(12,25),cv2.FONT_HERSHEY_SIMPLEX,.55,color,1,cv2.LINE_AA)
                    encoded_ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,65])
                    if encoded_ok:self.preview=base64.b64encode(encoded).decode('ascii');self.preview_time=time.monotonic()
                if self.context_shift:self.context_shift.observe_visual(self.arbiter.head_valid,hand_data.get('detected') and hand_data.get('control_ready'),hand_data)
                scroll_events=scroll.process(hand_data,time.monotonic())
                zoom_events = [translator.make_event("HAND",name,p) for name,p in zoom.process(None if hand_data.get('scroll_pose') else hand_data)]
                self.detail = "Head calibrated — return to neutral between gestures" if gestures.neutral else "Look straight ahead and hold still to calibrate"
                hand_events = translator.process_hand(hand_data)
                # Cancel loss before releases and suppress click throughout zoom/release.
                if not hand_data.get("detected"):
                    hand_events = [e for e in hand_events if e["action"] != "PINCH_END"]
                if zoom.state in ("ACTIVE","RELEASING"):
                    hand_events = [e for e in hand_events if e["action"] not in ("PINCH_START","PINCH_END")]
                if hand_data.get('scroll_pose'):
                    hand_events=[e for e in hand_events if e['action'] not in ('PINCH_START','PINCH_END','CURSOR_MOVE')]
                for event in zoom_events+events+hand_events+[translator.make_event('HAND',name,p) for name,p in scroll_events]:
                    self.publish(event)
        except Exception as exc:
            self.arbiter.hand_valid=False
            self.preview=None
            self.cancel()
            self.status("UNAVAILABLE", f"{type(exc).__name__}: {exc}")
        finally:
            if cap: cap.release()
            if head: head.close()
            if hand: hand.close()

    async def close(self):
        self.stop.set()
        if self.thread:
            await asyncio.to_thread(self.thread.join,3)
