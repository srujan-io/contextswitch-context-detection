
import time
import math

import cv2
import mediapipe as mp
import numpy as np

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from vision.pose_filter import OneEuro, matrix_pose


class HeadTracker:
    def __init__(self, model_path="models/face_landmarker.task"):
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(
                model_asset_path=model_path
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.4,
        )

        self.landmarker = vision.FaceLandmarker.create_from_options(
            options
        )

        self.start_time = time.monotonic()
        self.last_timestamp = -1

        self.last_seen = 0.0
        self.recovery_frames = 0
        self.recovery_required = 3
        self.filters = {axis: OneEuro() for axis in ("pitch","yaw","roll")}

    def process(self, frame):
        height, width = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)

        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb,
        )

        timestamp = int(
            (time.monotonic() - self.start_time) * 1000
        )
        timestamp = max(timestamp, self.last_timestamp + 1)
        self.last_timestamp = timestamp

        result = self.landmarker.detect_for_video(
            image, timestamp
        )

        if not result.face_landmarks or not result.facial_transformation_matrixes:
            self.recovery_frames = 0
            self.filters = {axis:OneEuro() for axis in ("pitch","yaw","roll")}
            return {
                "tracking_status": "LOST",
                "valid_for_actions": False,
            }

        lm = result.face_landmarks[0]

        def point(index):
            return np.array([
                lm[index].x * width,
                lm[index].y * height,
            ], dtype=np.float64)

        nose = point(1)
        chin = point(152)
        forehead = point(10)

        left_eye = point(33)
        right_eye = point(263)

        left_cheek = point(234)
        right_cheek = point(454)

        eye_center = (left_eye + right_eye) / 2
        face_center = (left_cheek + right_cheek) / 2

        face_width = np.linalg.norm(
            right_cheek - left_cheek
        )

        face_height = np.linalg.norm(
            chin - forehead
        )

        if face_width < 20 or face_height < 20:
            self.recovery_frames = 0
            return {
                "tracking_status": "LOST",
                "valid_for_actions": False,
            }

        pose = matrix_pose(result.facial_transformation_matrixes[0])
        now = time.monotonic()
        pose = {axis: round(self.filters[axis].update(value,now),2) for axis,value in pose.items()}

        self.recovery_frames += 1

        if self.recovery_frames < self.recovery_required:
            return {
                **pose,
                "tracking_status": "RECOVERING",
                "valid_for_actions": False,
            }

        return {
            **pose,
            "tracking_status": "TRACKING",
            "valid_for_actions": True,
        }

    def close(self):
        self.landmarker.close()
