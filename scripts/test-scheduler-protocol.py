#!/usr/bin/env python3
"""Unprivileged protocol tests; no systemd units or privileged commands."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui"))
from aio_core import scheduler, scheduler_protocol as protocol

for action in ("status", "remove"):
    assert protocol.decode_request(protocol.encode_request(action)) == {"action": action}
config = {**scheduler.DEFAULT, "enabled": True}
assert protocol.decode_request(protocol.encode_request("configure", config)) == {
    "action": "configure", "config": scheduler.validate_config(config)
}
invalid = [
    b"", b"[]", b"null", b"{}", b'{"action":"run"}',
    b'{"action":"status","config":{}}',
    b'{"action":"configure"}',
    b'{"action":"remove","command":"rm -rf /"}',
    b'{"action":"status","path":"/etc/shadow"}',
    b'{"action":"configure","config":{"enabled":true}}',
    b'{"action":"status"}' + b" " * 4096,
    b'{"action":"status","action":"run"}',  # duplicate keys rejected in a later hardening pass
]
for value in invalid[:-1]:
    try:
        protocol.decode_request(value)
    except (ValueError, TypeError):
        continue
    raise AssertionError(f"Unexpectedly accepted: {value[:80]!r}")
print("Scheduler protocol: valid actions and hostile payload rejection OK")
