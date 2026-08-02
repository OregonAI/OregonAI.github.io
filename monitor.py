#!/usr/bin/env python3
"""Synthetic monitor: is every corpus actually SERVING, right now, from outside?

  python3 monitor.py            # exit 0 all healthy, exit 1 with failures on stderr

Run by .github/workflows/monitor.yml on a 15-minute cron. This is the platform's only
end-to-end check: container healthchecks see the server from inside the host, the landing
page reports build-time facts about repos, and neither notices a wedged tunnel or a
route pointing at nothing. This POSTs a real JSON-RPC initialize through the public URL —
the same thing an agent's first request does — and asserts the corpus that answers is the
corpus the path names.

Stdlib only, same rule as build_site.py. Lives in this repo because it is public (free
Actions minutes) and because the site is already the platform's outward-facing surface;
platform-deploy is private.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "https://oregonai.morficflux.com"
TIMEOUT = 15

# route -> string that must appear in serverInfo.name. The tombstone is deliberately
# monitored too: a retired corpus's stub going dark is the exact failure the stub exists
# to prevent (an agent configured for the old corpus getting a transport error with no
# forwarding address).
ROUTES = {
    "executive-regulatory-frameworks": "executive-regulatory-frameworks",
    "oregon-legislature": "oregon-legislature",
    "oregon-budget": "oregon-budget",
    "oregon-audits": "oregon-audits",
    "oregon-kpm": "oregon-kpm",
    "oregon-counties": "oregon-counties",
    "federal-reference": "federal-reference",
    "oregon-records-retention": "oregon-records-retention",
}

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-03-26",
               "capabilities": {},
               "clientInfo": {"name": "oregonai-synthetic-monitor", "version": "1"}},
}


def body_json(raw: bytes, content_type: str) -> dict:
    """Streamable HTTP may answer as SSE (`data: {...}`) or plain JSON; accept both."""
    text = raw.decode("utf-8", "replace")
    if "text/event-stream" in content_type:
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("SSE response with no data: line")
    return json.loads(text)


def check(route: str, expect: str) -> str | None:
    """None if healthy, else a one-line failure description."""
    url = f"{BASE}/{route}/mcp"
    req = urllib.request.Request(
        url, data=json.dumps(INIT).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "User-Agent": "oregonai-synthetic-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return f"{route}: HTTP {r.status}"
            d = body_json(r.read(), r.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as e:
        return f"{route}: HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError,
            json.JSONDecodeError) as e:
        return f"{route}: {e}"
    name = ((d.get("result") or {}).get("serverInfo") or {}).get("name", "")
    if expect not in name:
        # The wrong corpus answering the path is WORSE than no answer — it means routing
        # is crossed, and every citation the caller resolves lands in the wrong corpus.
        return f"{route}: answered as {name!r}, expected it to contain {expect!r}"
    return None


def main() -> int:
    failures = [f for route, expect in ROUTES.items()
                if (f := check(route, expect))]
    for route in ROUTES:
        if not any(f.startswith(route + ":") for f in failures):
            print(f"  ok  {route}")
    if failures:
        print("\nFAILING:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"all {len(ROUTES)} routes healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
