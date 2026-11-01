"""Integration arbiter; no unavailable teammate selector is impersonated."""
import time


class Arbiter:
    def __init__(self):
        self.sensors = {s: {"status": "UNAVAILABLE", "timestamp": 0} for s in ("CAMERA", "MICROPHONE", "IMU")}
        self.active = "HEAD_HAND"
        self.zoom_until = 0
        self.head_valid=False
        self.hand_valid=True
        self.scroll_until=0.

    def status(self, sensor, status):
        self.sensors[sensor] = {"status": status, "timestamp": int(time.time()*1000)}
        if sensor == "CAMERA" and status != "TRACKING":
            self.zoom_until = 0

    def snapshot(self):
        camera = self.sensors["CAMERA"]
        if camera["status"] not in ("UNAVAILABLE", "PAUSED") and time.time()*1000-camera["timestamp"] > 4500:
            self.status("CAMERA", "LOST")
            camera = self.sensors["CAMERA"]
        recommended = "HEAD_HAND" if camera["status"] == "TRACKING" else "TYPED"
        if camera['status']!='TRACKING' and self.head_valid and self.sensors['IMU']['status']=='TRACKING':recommended='HEAD'
        return {"sensors": self.sensors, "active_modality": self.active, "recommended_modality": recommended,
                "recommendation_only": True, "imu_detail": "Pico V1 decoder available; see IMU/fusion diagnostics"}

    def allow(self, event, busy=False):
        action = event.get("action")
        if action in ("TRACKING_LOST", "PINCH_CANCEL", "PINCH_ZOOM_END"):
            self.zoom_until = 0
            self.scroll_until=0.
            return True
        stamp = event.get("timestamp", 0)
        if not isinstance(stamp, (int,float)) or not 0 <= time.time()*1000-stamp <= 700:
            return False
        valid = self.head_valid if event.get('source')=='HEAD' else self.hand_valid and self.sensors['CAMERA']['status']=='TRACKING'
        if busy or self.active not in ("HEAD_HAND", event.get("source")) or not valid:
            return False
        if action in ("PINCH_ZOOM_START", "PINCH_ZOOM"):
            self.zoom_until = time.monotonic()+1
        if action=='SCROLL':self.scroll_until=time.monotonic()+.4
        if event.get('source')=='HEAD' and time.monotonic()<self.scroll_until:return False
        if event.get("source") == "HEAD" and action in ("HEAD_TILT_LEFT", "HEAD_TILT_RIGHT") and time.monotonic() < self.zoom_until:
            return False
        return True
