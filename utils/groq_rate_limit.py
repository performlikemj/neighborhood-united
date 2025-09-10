import os
import time
import random
import re
from threading import Semaphore

# Simple, process-local concurrency gate for Groq calls
_GROQ_SEMA = Semaphore(int(os.getenv("GROQ_MAX_INFLIGHT", "2")))


def parse_duration(s: str) -> float:
    """Parse durations like '7.66s', '2m59.56s', '1h2m3s' to seconds."""
    if not s:
        return 1.0
    # full matcher: optional h, optional m, optional s
    m = re.match(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?$", s)
    if m:
        h, m_, s_ = (float(x) if x else 0.0 for x in m.groups())
        return h * 3600 + m_ * 60 + s_
    # fallback for simple '<secs>s'
    m2 = re.match(r"([\d.]+)s$", s)
    if m2:
        return float(m2.group(1))
    return 1.0


def groq_call_with_retry(raw_create_fn, create_fn, desc: str, max_retries=4, base_sleep=1.0, **kwargs):
    """
    Generic Groq call wrapper with:
    - Optional with_raw_response path to read rate headers
    - 429 handling using retry-after or x-ratelimit-reset-* headers
    - Exponential backoff fallback with jitter
    - Basic stdout diagnostics for testing

    Returns the parsed response object (same shape as create_fn).
    """
    with _GROQ_SEMA:
        for attempt in range(max_retries + 1):
            # Prefer raw path
            if raw_create_fn:
                try:
                    raw = raw_create_fn(**kwargs)
                    if raw.status_code == 200:
                        hdr = getattr(raw, "headers", {}) or {}
                        try:
                            print(
                                f"][rate] {desc}: 200 attempt={attempt} "
                                f"rem-req={hdr.get('x-ratelimit-remaining-requests')} rem-tok={hdr.get('x-ratelimit-remaining-tokens')} "
                                f"reset-req={hdr.get('x-ratelimit-reset-requests')} reset-tok={hdr.get('x-ratelimit-reset-tokens')}"
                            )
                        except Exception:
                            pass
                        return raw.parse()
                    if raw.status_code == 429:
                        hdr = getattr(raw, "headers", {}) or {}
                        wait = hdr.get("retry-after") or hdr.get("x-ratelimit-reset-tokens") or hdr.get("x-ratelimit-reset-requests")
                        sleep_for = float(wait) if (wait and str(wait).isdigit()) else parse_duration(str(wait or ""))
                        sleep_for = max(sleep_for, base_sleep)
                        try:
                            print(
                                f"] {desc}: 429 attempt={attempt} sleep={sleep_for:.2f}s "
                                f"rem-req={hdr.get('x-ratelimit-remaining-requests')} rem-tok={hdr.get('x-ratelimit-remaining-tokens')}"
                            )
                        except Exception:
                            pass
                        time.sleep(sleep_for)
                        continue
                    # Other errors – print and raise
                    try:
                        body_preview = getattr(raw, "text", "")[:200]
                        print(f"] {desc}: status={raw.status_code} body={body_preview}")
                    except Exception:
                        pass
                    raw.raise_for_status()
                except Exception as e:
                    # Fall back to non-raw path with backoff logic below
                    try:
                        print(f"] {desc}: raw path exception: {e}")
                    except Exception:
                        pass

            # Non-raw path
            try:
                resp = create_fn(**kwargs)
                try:
                    print(f"] {desc}: non-raw success attempt={attempt}")
                except Exception:
                    pass
                return resp
            except Exception as e:
                msg = str(e)
                if "429" in msg and attempt < max_retries:
                    sleep_for = base_sleep * (2 ** attempt) * (1.0 + random.uniform(0, 0.2))
                    try:
                        print(f"] {desc}: exception 429 attempt={attempt} sleep={sleep_for:.2f}s")
                    except Exception:
                        pass
                    time.sleep(sleep_for)
                    continue
                try:
                    print(f"] {desc}: non-raw exception: {e}")
                except Exception:
                    pass
                raise

