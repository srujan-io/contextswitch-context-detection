"""One-frame camera + 200 ms microphone capture. No recording retained or sent."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"backend"))
result = {}
try:
    import cv2
    from vision.head_tracker import HeadTracker
    from vision.hand_tracker import HandTracker
    cap = cv2.VideoCapture(int(os.getenv("BEYOND_TOUCH_CAMERA_INDEX","0")),cv2.CAP_DSHOW)
    try:
        ok, frame = cap.read()
        if not ok: raise RuntimeError("No camera frame captured")
        models=Path(__file__).parents[1]/"backend/models"
        head=HeadTracker(str(models/"face_landmarker.task"))
        hand=HandTracker(str(models/"hand_landmarker.task"))
        try:
            pose=head.process(frame); fingers=hand.process(frame)
            result['camera']={'frame_captured':True,'models_loaded':True,'head_status':pose.get('tracking_status'),'hand_detected':fingers.get('detected'),'live_gestures_verified':False}
        finally: head.close();hand.close()
    finally: cap.release()
except Exception as exc:
    result['camera']={'frame_captured':False,'error':f'{type(exc).__name__}: {exc}'}
try:
    import speech_recognition as sr
    with sr.Microphone(device_index=int(os.environ['BEYOND_TOUCH_MIC_INDEX']) if os.getenv('BEYOND_TOUCH_MIC_INDEX') else None) as source:
        audio=sr.Recognizer().record(source,duration=.2)
    result['microphone']={'capture_succeeded':bool(audio.frame_data),'asr_verified':False,'bytes_captured':len(audio.frame_data)}
except Exception as exc:
    result['microphone']={'capture_succeeded':False,'error':f'{type(exc).__name__}: {exc}'}
result['imu']={'verified':False,'detail':'No implemented firmware or serial contract supplied'}
out=Path(__file__).parents[1]/'HARDWARE_PROBE.json'
out.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
