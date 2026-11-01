"""Voice quality state, noise buckets, status events, and local heartbeat logging."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable

from settings import Settings

STATUS_OUTPUT_LOCK = threading.Lock()


class VoiceStatusMonitor:
    """Windowed ASR/noise monitor with hysteresis and dwell-based recovery."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.quality = "GOOD"
        self.noise_level = "UNKNOWN"
        self.noise_ratio: float | None = None
        self.failure_count_in_window = 0
        self.reason = "NO_UTTERANCE_YET"
        self._outcomes: deque[bool] = deque(maxlen=settings.voice_asr_failure_window)
        self._clean_utterances = 0
        self._pending_uncertain_since: float | None = None
        self._pending_recovery_since: float | None = None
        self._lock = threading.RLock()
        self._callback: Callable[[dict[str, Any]], None] | None = None
        self._last_signature: tuple[Any, ...] | None = None

    def set_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._callback = callback
        self._publish(force=True)

    def observe_noise(self, rms: float) -> None:
        with self._lock:
            settings = self.settings
            calibrated = (
                settings.voice_thresholds_calibrated
                and settings.voice_noise_baseline_rms is not None
                and settings.voice_noise_baseline_rms > 0
                and settings.voice_noise_low_max_ratio is not None
                and settings.voice_noise_med_max_ratio is not None
                and settings.voice_noise_enter_ratio is not None
                and settings.voice_noise_exit_ratio is not None
                and settings.voice_noise_med_max_ratio > settings.voice_noise_low_max_ratio > 0
                and settings.voice_noise_enter_ratio > settings.voice_noise_exit_ratio > 0
            )
            if calibrated:
                self.noise_ratio = max(0.0, rms) / settings.voice_noise_baseline_rms  # type: ignore[operator]
                if self.noise_ratio <= settings.voice_noise_low_max_ratio:
                    self.noise_level = "LOW"
                elif self.noise_ratio <= settings.voice_noise_med_max_ratio:
                    self.noise_level = "MED"
                else:
                    self.noise_level = "HIGH"
                self.reason = "AMBIENT_MEASURED"
            else:
                self.noise_level = "UNKNOWN"
                self.noise_ratio = None
                self.reason = "NOISE_THRESHOLDS_UNCALIBRATED"
            self._evaluate_locked(time.monotonic())
        self._publish()

    def record_asr_success(self) -> None:
        with self._lock:
            self._outcomes.append(False)
            self._refresh_failure_count_locked()
            noise_is_clean = self.noise_ratio is None or self.noise_ratio <= self.settings.voice_noise_exit_ratio
            self._clean_utterances = self._clean_utterances + 1 if noise_is_clean else 0
            self.reason = "ASR_SUCCESS"
            self._evaluate_locked(time.monotonic())
        self._publish()

    def record_asr_failure(self, reason: str, *, unavailable: bool = False,
                           count_toward_uncertain: bool = True) -> None:
        with self._lock:
            if count_toward_uncertain:
                self._outcomes.append(True)
                self._refresh_failure_count_locked()
            self._clean_utterances = 0
            self.reason = reason
            if unavailable:
                self.quality = "UNAVAILABLE"
                self._pending_uncertain_since = None
                self._pending_recovery_since = None
            self._evaluate_locked(time.monotonic())
        self._publish()

    def mark_unavailable(self, reason: str) -> None:
        with self._lock:
            self.quality = "UNAVAILABLE"
            self.reason = reason
            self._clean_utterances = 0
            self._pending_uncertain_since = None
            self._pending_recovery_since = None
        self._publish()

    def heartbeat(self) -> None:
        with self._lock:
            self._evaluate_locked(time.monotonic())
        self._publish(force=True)

    def metadata(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._event_locked()["metadata"])

    def _refresh_failure_count_locked(self) -> None:
        self.failure_count_in_window = sum(self._outcomes)

    def _evaluate_locked(self, now: float) -> None:
        noise_triggered = (
            self.noise_ratio is not None
            and self.noise_ratio >= self.settings.voice_noise_enter_ratio
        )
        failures_triggered = self.failure_count_in_window >= self.settings.voice_asr_failures_to_uncertain
        should_be_uncertain = noise_triggered or failures_triggered
        dwell = self.settings.voice_status_min_dwell_seconds

        if self.quality == "GOOD":
            if should_be_uncertain:
                if self._pending_uncertain_since is None:
                    self._pending_uncertain_since = now
                if now - self._pending_uncertain_since >= dwell:
                    self.quality = "UNCERTAIN"
                    if noise_triggered:
                        self.reason = "HIGH_NOISE"
                    elif not self.reason.startswith("ASR_") and self.reason != "NO_SPEECH_TIMEOUT":
                        self.reason = "ASR_FAILURES"
                    self._pending_uncertain_since = None
            else:
                self._pending_uncertain_since = None
                if self.reason in {"HIGH_NOISE", "ASR_FAILURES"}:
                    self.reason = "NORMAL"
            return

        noise_is_clean = self.noise_ratio is None or self.noise_ratio <= self.settings.voice_noise_exit_ratio
        failures_are_clear = self.failure_count_in_window < self.settings.voice_asr_failures_to_uncertain
        can_recover = (
            self._clean_utterances >= self.settings.voice_clean_utterances_to_recover
            and noise_is_clean
            and failures_are_clear
        )
        if can_recover:
            if self._pending_recovery_since is None:
                self._pending_recovery_since = now
            if now - self._pending_recovery_since >= dwell:
                self.quality = "GOOD"
                self.reason = "RECOVERED"
                self._pending_recovery_since = None
                self._pending_uncertain_since = None
        else:
            self._pending_recovery_since = None

    def _event_locked(self) -> dict[str, Any]:
        return {
            "source": "VOICE",
            "type": "STATUS",
            "text": "",
            "timestamp": int(time.time() * 1000),
            "metadata": {
                "quality": self.quality,
                "noise_level": self.noise_level,
                "noise_ratio": round(self.noise_ratio, 4) if self.noise_ratio is not None else None,
                "failure_count_in_window": self.failure_count_in_window,
                "reason": self.reason,
            },
        }

    def _publish(self, force: bool = False) -> None:
        with self._lock:
            event = self._event_locked()
            meta = event["metadata"]
            signature = (meta["quality"], meta["noise_level"], meta["noise_ratio"],
                         meta["failure_count_in_window"], meta["reason"])
            if not force and signature == self._last_signature:
                return
            self._last_signature = signature
            callback = self._callback
        if callback is not None:
            callback(event)


class VoiceStatusReporter:
    """Emit status changes and slow heartbeats to stdout and a local JSONL log."""

    def __init__(self, monitor: VoiceStatusMonitor, interval_seconds: float | None = None,
                 log_path: str | Path | None = None):
        self.monitor = monitor
        self.interval_seconds = interval_seconds or monitor.settings.voice_status_heartbeat_seconds
        self.log_path = Path(log_path) if log_path else Path(__file__).parent / "data" / "logs" / "voice_status.jsonl"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._io_lock = STATUS_OUTPUT_LOCK

    def start(self) -> None:
        self.monitor.set_callback(self._emit)
        self._thread = threading.Thread(target=self._heartbeat_loop, name="voice-status-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.monitor.heartbeat()

    def _emit(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._io_lock:
            print(line, flush=True)
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as stream:
                    stream.write(line + "\n")
            except OSError as exc:
                print(f"Voice status local logging failed ({type(exc).__name__}).", flush=True)
