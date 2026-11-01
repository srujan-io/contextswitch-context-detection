"""Measure quiet-room and noisy-room microphone RMS for manual threshold selection."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any


def _rms_samples(source: Any, seconds: float, np: Any) -> float:
    chunk_size = int(source.CHUNK)
    sample_rate = int(source.SAMPLE_RATE)
    chunk_count = max(1, math.ceil(seconds * sample_rate / chunk_size))
    chunks = []
    for _ in range(chunk_count):
        data = source.stream.read(chunk_size)
        width = int(source.SAMPLE_WIDTH)
        if width == 1:
            samples = np.frombuffer(data, dtype=np.uint8).astype(np.float64) - 128.0
        elif width == 2:
            samples = np.frombuffer(data, dtype="<i2").astype(np.float64)
        elif width == 3:
            raw = np.frombuffer(data[:len(data) - len(data) % 3], dtype=np.uint8).reshape(-1, 3)
            values = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
            samples = ((values ^ 0x800000) - 0x800000).astype(np.float64)
        elif width == 4:
            samples = np.frombuffer(data, dtype="<i4").astype(np.float64)
        else:
            raise ValueError(f"Unsupported microphone sample width: {width}")
        if samples.size:
            chunks.append(samples)
    if not chunks:
        return 0.0
    samples = np.concatenate(chunks)
    return float(np.sqrt(np.mean(np.square(samples))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5.0, help="Capture duration for each environment")
    parser.add_argument("--device-index", type=int, help="Optional SpeechRecognition microphone index")
    args = parser.parse_args(argv)
    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")

    try:
        import numpy as np
        import speech_recognition as sr
    except ImportError as exc:
        print(f"Calibration dependencies unavailable: {exc}", file=sys.stderr)
        return 1

    try:
        with sr.Microphone(device_index=args.device_index) as source:
            input("Turn off fan/music and keep quiet. Press Enter to measure the quiet baseline...")
            quiet_values = _rms_samples(source, args.seconds, np)
            input("Turn on the fan/music at the intended test level. Press Enter to measure noise...")
            noisy_values = _rms_samples(source, args.seconds, np)
    except Exception as exc:
        print(f"Microphone calibration failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

    quiet_rms = quiet_values
    noisy_rms = noisy_values
    ratio = noisy_rms / max(quiet_rms, 1.0)
    print(f"Quiet baseline RMS: {quiet_rms:.2f}")
    print(f"Noisy RMS: {noisy_rms:.2f}")
    print(f"Noisy/quiet ratio: {ratio:.3f}")
    print("Choose LOW/MED and MED/HIGH ratios between the quiet and noisy measurements,")
    print("then set enter/exit ratios with hysteresis. Add these values to member3/.env:")
    print(f"VOICE_NOISE_BASELINE_RMS={quiet_rms:.2f}")
    print("VOICE_NOISE_LOW_MAX_RATIO=<calibrated cutoff>")
    print("VOICE_NOISE_MED_MAX_RATIO=<calibrated cutoff>")
    print("VOICE_NOISE_ENTER_RATIO=<higher enter cutoff>")
    print("VOICE_NOISE_EXIT_RATIO=<lower recovery cutoff>")
    print("VOICE_THRESHOLDS_CALIBRATED=true")
    print("Repeat with Windows mic noise suppression enabled and disabled if applicable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
