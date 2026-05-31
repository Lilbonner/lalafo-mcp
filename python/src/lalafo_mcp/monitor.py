"""Standalone monitor: periodically check subscriptions and push notifications.

  python -m lalafo_mcp.monitor --once   # single pass (for cron / Task Scheduler)
  python -m lalafo_mcp.monitor          # loop every MONITOR_INTERVAL seconds (default 600)

Shares the subscription store with the MCP server, so subscriptions created via the
`subscribe` tool are picked up here automatically.
"""
import os
import sys
import time

from . import notify, subscriptions


def run_once() -> int:
    res = subscriptions.check(notify_channels=True)
    total_new = sum(s.get("new_count", 0) for s in res["subscriptions"])
    chans = notify.configured_channels() or ["(none — only printed)"]
    print(f"[monitor] checked {res['checked']} subscription(s), {total_new} new; channels: {', '.join(chans)}")
    for s in res["subscriptions"]:
        if s.get("new_count"):
            print(f"  + {s['name']}: {s['new_count']} new")
    return total_new


def main() -> None:
    if "--once" in sys.argv:
        run_once()
        return
    interval = int(os.getenv("MONITOR_INTERVAL", "600"))
    print(f"[monitor] polling every {interval}s (Ctrl+C to stop)")
    while True:
        try:
            run_once()
        except Exception as e:  # keep the loop alive on transient failures
            print(f"[monitor] error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
