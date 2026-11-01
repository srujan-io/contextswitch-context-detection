
import time
import math
from pathlib import Path

import cv2
import mediapipe as mp
from vision.hand_availability import assess_hands
from vision.hand_render import draw_hands


class HandTracker:
    def __init__(self, model_path="models/hand_landmarker.task"):
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Hand model not found: {model_path.resolve()}"
            )

        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        self.landmarker = HandLandmarker.create_from_options(options)
        self.start_time = time.monotonic()
        self.last_timestamp = -1

        self.pinch_active = False
        self.primary_label=None
        self.pinch_start_threshold = 0.32
        self.pinch_release_threshold = 0.45

        self.connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17)
        ]

    def process(self, frame):
        height, width = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp = int(
            (time.monotonic() - self.start_time) * 1000
        )
        timestamp = max(timestamp, self.last_timestamp + 1)
        self.last_timestamp = timestamp

        result = self.landmarker.detect_for_video(
            image, timestamp
        )

        if not result.hand_landmarks:
            self.pinch_active = False
            return {
                "detected": False,
                "index_x": None,
                "index_y": None,
                "pinching": False,
                "pinch_event": None,
                "pinch_ratio": None,
                **assess_hands([]),
            }

        availability=assess_hands(result.hand_landmarks)
        labels=[result.handedness[i][0].category_name if i<len(result.handedness) and result.handedness[i] else str(i) for i in range(len(result.hand_landmarks))]
        primary=labels.index(self.primary_label) if self.primary_label in labels else 0
        if not availability['hands'][primary]['fully_visible']:
            primary=next((i for i,h in enumerate(availability['hands']) if h['fully_visible']),primary)
        changed=self.primary_label is not None and labels[primary]!=self.primary_label
        if changed:self.pinch_active=False
        self.primary_label=labels[primary]
        landmarks = result.hand_landmarks[primary]
        draw_hands(frame,result.hand_landmarks,labels,primary,availability,self.connections,cv2)
        if not availability['hands'][primary]['fully_visible']:
            self.pinch_active=False
            return {'detected':False,'pinching':False,'index_x':None,'index_y':None,**availability}
        # Index + middle extended, ring + pinky curled. Thumb does not arm scroll.
        scroll_pose = (landmarks[8].y < landmarks[6].y and landmarks[12].y < landmarks[10].y
                       and landmarks[16].y > landmarks[14].y and landmarks[20].y > landmarks[18].y)

        # Index fingertip = 8, thumb tip = 4
        index = landmarks[8]
        thumb = landmarks[4]

        # Hand width used to normalize pinch distance
        index_base = landmarks[5]
        pinky_base = landmarks[17]

        hand_width = math.hypot(
            index_base.x - pinky_base.x,
            index_base.y - pinky_base.y
        )

        pinch_distance = math.hypot(
            index.x - thumb.x,
            index.y - thumb.y
        )

        pinch_ratio = pinch_distance / max(hand_width, 1e-6)

        pinch_event = None

        if not self.pinch_active:
            if pinch_ratio < self.pinch_start_threshold:
                self.pinch_active = True
                pinch_event = "PINCH_START"
        else:
            if pinch_ratio > self.pinch_release_threshold:
                self.pinch_active = False
                pinch_event = "PINCH_END"

        # Highlight fingertip
        ix = int(index.x * width)
        iy = int(index.y * height)

        cv2.circle(
            frame,
            (ix, iy),
            12,
            (0, 0, 255) if self.pinch_active else (0, 255, 0),
            2
        )

        return {
            "detected": True,
            "index_x": float(index.x),
            "index_y": float(index.y),
            "pinching": self.pinch_active,
            "pinch_event": pinch_event,
            "pinch_ratio": round(pinch_ratio, 3),
            "scroll_pose": bool(scroll_pose),
            "control_ready": bool(landmarks[8].y < landmarks[6].y),
            "control_hand_changed":changed,
            **availability,
        }

    def close(self):
        self.landmarker.close()

