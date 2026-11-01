"""Manual plumbing check: one Gemini response and one local sentence vector."""

from __future__ import annotations

import sys
import re

from matcher import FastEmbedEncoder
from settings import create_gemini_client, load_settings


def main() -> int:
    client = None
    try:
        settings = load_settings()
    except Exception as exc:
        print(f"Configuration load failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    try:
        client = create_gemini_client(settings)
    except RuntimeError as exc:
        safe_messages = {
            "GEMINI_API_KEY is not configured in member3/.env",
            "google-genai is not installed; install member3/requirements.txt",
        }
        message = str(exc)
        if message in safe_messages:
            print(f"Gemini SDK setup failed: {message}", file=sys.stderr)
        else:
            print(f"Gemini SDK setup failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Gemini SDK setup failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    try:
        response = client.models.generate_content(
            model=settings.model,
            contents="Reply with exactly: GEMINI_OK",
            config={"temperature": 0, "max_output_tokens": 16},
        )
        print("Gemini smoke response:", (getattr(response, "text", "") or "").strip())
    except Exception as exc:
        print("Gemini request failed:", _safe_exception_summary(exc, settings.api_key), file=sys.stderr)
        return 1
    try:
        encoder = FastEmbedEncoder(settings.embedding_model)
        vector = encoder.encode(["Find the USB connector"])[0]
        print("Sentence embedding dimension:", len(vector))
        return 0
    except RuntimeError as exc:
        print(f"Embedding setup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Embedding/model download failed ({type(exc).__name__}); check network and FastEmbed model access.", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


def _safe_exception_summary(exc: Exception, api_key: str | None) -> str:
    """Expose actionable API errors without printing credentials or headers."""
    parts = [type(exc).__name__]
    response = getattr(exc, "response", None)
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code is None and response is not None:
        code = getattr(response, "status_code", None)
    status = getattr(exc, "status", None)
    if code is not None:
        parts.append(f"HTTP {code}")
    if status and str(status) not in parts:
        parts.append(str(status))
    detail = str(getattr(exc, "message", None) or exc)
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED_KEY]", detail)
    detail = re.sub(r"https?://\S+", "[URL REDACTED]", detail)
    detail = re.sub(r"(?im)^.*(?:authorization|x-goog-api-key|api[_ -]?key).*$", "[CREDENTIAL DETAIL REDACTED]", detail)
    detail = re.sub(r"(?i)(?:key|api_key)\s*[=:]\s*[^,\s}]+", "key=[REDACTED]", detail)
    detail = " ".join(detail.split())[:500]
    return " — ".join(parts) + (f": {detail}" if detail else "")


if __name__ == "__main__":
    raise SystemExit(main())
