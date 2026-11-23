"""Validated, format-independent protocol for the host maintenance scheduler.

This module contains no privilege escalation. The privileged host service must
validate the same request again before applying any change.
"""
import json

from . import scheduler

ACTIONS = frozenset(("status", "configure", "remove"))
MAX_REQUEST_BYTES = 4096


def decode_request(raw):
    """Parse one untrusted JSON request; never accept shell commands or paths."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Invalid scheduler request size.")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid scheduler request JSON.") from exc
    if not isinstance(request, dict) or set(request) - {"action", "config"}:
        raise ValueError("Invalid scheduler request fields.")
    action = request.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("Unsupported scheduler action.")
    if action == "configure":
        if set(request) != {"action", "config"}:
            raise ValueError("Missing scheduler configuration.")
        return {"action": action, "config": scheduler.validate_config(request["config"])}
    if set(request) != {"action"}:
        raise ValueError("Unexpected scheduler configuration.")
    return {"action": action}


def encode_request(action, config=None):
    request = {"action": action}
    if config is not None:
        request["config"] = config
    return json.dumps(decode_request(json.dumps(request).encode("utf-8")),
                      separators=(",", ":")).encode("utf-8") + b"\n"
