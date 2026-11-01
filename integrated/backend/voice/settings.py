"""Centralized environment and Gemini client setup; never logs credentials."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ENV_FILE = Path(__file__).with_name(".env")
GEMINI_TIMEOUT_MS = 30_000  # The API rejected 3s and the service timed out at 10s.


def _load_local_env() -> None:
    """Load this package's .env once; allow operation without python-dotenv."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=False)
        return
    except ImportError:
        pass
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, content = value.split("=", 1)
        os.environ.setdefault(key.strip(), content.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    embedding_model: str
    voice_thresholds_calibrated: bool = False
    voice_noise_baseline_rms: float | None = None
    voice_noise_low_max_ratio: float | None = None
    voice_noise_med_max_ratio: float | None = None
    voice_noise_enter_ratio: float | None = None
    voice_noise_exit_ratio: float | None = None
    voice_status_min_dwell_seconds: float = 5.0
    voice_status_heartbeat_seconds: float = 15.0
    voice_asr_failure_window: int = 5
    voice_asr_failures_to_uncertain: int = 2
    voice_clean_utterances_to_recover: int = 2


def _env_float(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be at least 1")
    return value


def load_settings() -> Settings:
    _load_local_env()
    noise_baseline = _env_float("VOICE_NOISE_BASELINE_RMS", None)
    settings = Settings(
        api_key=os.environ.get("GEMINI_API_KEY"),
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        embedding_model=os.environ.get("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        voice_thresholds_calibrated=os.environ.get("VOICE_THRESHOLDS_CALIBRATED", "false").strip().lower() == "true",
        voice_noise_baseline_rms=noise_baseline,
        voice_noise_low_max_ratio=_env_float("VOICE_NOISE_LOW_MAX_RATIO", None),
        voice_noise_med_max_ratio=_env_float("VOICE_NOISE_MED_MAX_RATIO", None),
        voice_noise_enter_ratio=_env_float("VOICE_NOISE_ENTER_RATIO", None),
        voice_noise_exit_ratio=_env_float("VOICE_NOISE_EXIT_RATIO", None),
        voice_status_min_dwell_seconds=float(_env_float("VOICE_STATUS_MIN_DWELL_SECONDS", 5.0)),
        voice_status_heartbeat_seconds=float(_env_float("VOICE_STATUS_HEARTBEAT_SECONDS", 15.0)),
        voice_asr_failure_window=_env_int("VOICE_ASR_FAILURE_WINDOW", 5),
        voice_asr_failures_to_uncertain=_env_int("VOICE_ASR_FAILURES_TO_UNCERTAIN", 2),
        voice_clean_utterances_to_recover=_env_int("VOICE_CLEAN_UTTERANCES_TO_RECOVER", 2),
    )
    if settings.voice_status_min_dwell_seconds <= 0:
        raise RuntimeError("VOICE_STATUS_MIN_DWELL_SECONDS must be greater than zero")
    if settings.voice_status_heartbeat_seconds <= 0:
        raise RuntimeError("VOICE_STATUS_HEARTBEAT_SECONDS must be greater than zero")
    if settings.voice_asr_failure_window < 2 or settings.voice_asr_failures_to_uncertain < 2:
        raise RuntimeError("ASR uncertainty requires a window and failure threshold of at least 2")
    if settings.voice_asr_failures_to_uncertain > settings.voice_asr_failure_window:
        raise RuntimeError("VOICE_ASR_FAILURES_TO_UNCERTAIN cannot exceed VOICE_ASR_FAILURE_WINDOW")
    if settings.voice_clean_utterances_to_recover < 2:
        raise RuntimeError("VOICE_CLEAN_UTTERANCES_TO_RECOVER must be at least 2")
    return settings


def create_gemini_client(settings: Settings | None = None):
    settings = settings or load_settings()
    if not settings.api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in member3/.env")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed; install member3/requirements.txt") from exc
    return genai.Client(
        api_key=settings.api_key,
        http_options=types.HttpOptions(
            timeout=GEMINI_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
