#!/usr/bin/env python3
"""
Create Microblink Platform verification links.

Usage:
    python3 vlink.py            # create a link (runs init first if not configured)
    python3 vlink.py init       # (re)configure; Enter keeps each saved value
    python3 vlink.py workflow   # change only the workflowId

Requires only Python 3.7+ (standard library). Works on Linux, macOS and Windows.
Docs: https://docs.microblink.com/platform/api/verification-links
See VLINK.md for full instructions.
"""

import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGIONS = [
    ("us-east", "US East", "https://api.us-east.platform.microblink.com/agent/api/v1/verification-link"),
    ("eu", "EU", "https://api.eu.platform.microblink.com/agent/api/v1/verification-link"),
]
DEFAULT_REGION = "us-east"
CONFIG_PATH = Path.home() / ".microblink-vlink.json"
DEFAULT_TTL_HOURS = 24


def command_name():
    # How the user started the script, e.g. "python3 vlink.py" or "py vlink.py", on any OS.
    return "{} {}".format(Path(sys.executable).stem or "python", Path(sys.argv[0]).name or "vlink.py")


def usage():
    cmd = command_name()
    return "\n".join([
        "Usage:",
        "  {}            create a verification link".format(cmd),
        "  {} init       change the saved settings (Enter keeps each value)".format(cmd),
        "  {} workflow   change only the workflowId".format(cmd),
    ])


def to_iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ask(label, current=None, secret=False):
    hint = " [Enter = keep current]" if current else ""
    while True:
        prompt = "{}{}: ".format(label, hint)
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if value:
            return value
        if current:
            return current
        print("  Value is required.")


def region_info(key):
    for region in REGIONS:
        if region[0] == key:
            return region
    return region_info(DEFAULT_REGION)


def ask_region(current=None):
    marker = "  (current)" if current else "  (default)"
    current = region_info(current)[0]
    print("Region:")
    for number, (key, name, _) in enumerate(REGIONS, start=1):
        print("  {}) {}{}".format(number, name, marker if key == current else ""))
    while True:
        raw = input("Select region [Enter = {}]: ".format(region_info(current)[1])).strip().lower()
        if not raw:
            return current
        numbers = [str(n) for n in range(1, len(REGIONS) + 1)]
        if raw in numbers:
            return REGIONS[numbers.index(raw)][0]
        for key, name, _ in REGIONS:
            if raw in (key, name.lower()):
                return key
        print("  Enter a number from 1 to {}.".format(len(REGIONS)))


def ask_expires_in_hours(current=None):
    current = current or DEFAULT_TTL_HOURS
    while True:
        raw = input("expiresOn - hours after each link's creation [Enter = {}]: ".format(format_hours(current))).strip()
        if not raw:
            return current
        try:
            hours = float(raw)
        except ValueError:
            print("  Enter a number of hours, e.g. 24 or 1.5.")
            continue
        if hours <= 0:
            print("  Hours must be greater than 0; using the default of {}h.".format(DEFAULT_TTL_HOURS))
            return DEFAULT_TTL_HOURS
        return hours


def format_hours(hours):
    return "{:g}".format(hours)


def load_config():
    if not CONFIG_PATH.exists():
        return None
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)  # owner read/write only; Windows keeps its profile-folder permissions
    except OSError:
        pass


def init(existing=None):
    existing = existing or {}
    print("Configuring verification-link client (saved to {})".format(CONFIG_PATH))
    cfg = {
        "region": ask_region(existing.get("region")),
        "clientId": ask("clientId", existing.get("clientId")),
        "clientSecret": ask("clientSecret (hidden)", existing.get("clientSecret"), secret=True),
        "workflowId": ask("workflowId", existing.get("workflowId")),
        "expiresInHours": ask_expires_in_hours(existing.get("expiresInHours")),
    }
    save_config(cfg)
    print("Saved.\n")
    return cfg


def change_workflow(cfg):
    print("Region: {} | clientId: {}".format(region_info(cfg.get("region"))[1], cfg.get("clientId")))
    cfg["workflowId"] = ask("workflowId", cfg.get("workflowId"))
    save_config(cfg)
    print("Saved.\n")
    return cfg


def resolve_expires_on(cfg, created_at):
    hours = cfg.get("expiresInHours")
    if not isinstance(hours, (int, float)) or hours <= 0:
        hours = DEFAULT_TTL_HOURS
    return to_iso(created_at + timedelta(hours=hours))


def create_link(cfg, user_id):
    created_at = datetime.now(timezone.utc)
    body = {
        "expiresOn": resolve_expires_on(cfg, created_at),
        "workflowId": cfg["workflowId"],
        "consent": {
            "userId": user_id,
            "givenOn": to_iso(created_at),
            "isProcessingStoringAllowed": True
        },
    }
    token = base64.b64encode("{}:{}".format(cfg["clientId"], cfg["clientSecret"]).encode()).decode()
    req = urllib.request.Request(
        region_info(cfg.get("region"))[2],
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Basic " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.reason, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.reason, e.read().decode("utf-8", errors="replace")


def format_body(text):
    try:
        return json.dumps(json.loads(text), indent=2)
    except ValueError:
        return text.strip() or "(empty response body)"


def error_message(text):
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("detail", "message", "title", "error_description", "error"):
        if isinstance(data.get(key), str) and data[key]:
            return data[key]
    return None


def main():
    # Never crash on characters the terminal's encoding can't show (e.g. a legacy Windows code page).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = [a.lower() for a in sys.argv[1:]]
    command = args[0] if args else None
    if len(args) > 1 or command not in (None, "init", "workflow"):
        print(usage(), file=sys.stderr)
        return 2

    cfg = load_config()
    if command == "init":
        init(cfg)
        return 0
    if cfg is None:
        cfg = init()
    elif command == "workflow":
        change_workflow(cfg)
        return 0

    user_id = ask("userId")
    try:
        status, reason, text = create_link(cfg, user_id)
    except urllib.error.URLError as e:
        print("Error: could not reach the server: {}".format(e.reason), file=sys.stderr)
        return 1

    if status == 200:
        try:
            data = json.loads(text)
            # The live API returns "url"; the docs show "address".
            link = data.get("url") or data.get("address")
        except (ValueError, AttributeError):
            link = None
        if link:
            print(link)
            return 0
        print("Error: HTTP 200 but the response contains no link.", file=sys.stderr)
    else:
        message = error_message(text)
        print("Error: HTTP {} {}{}".format(status, reason, " - " + message if message else ""), file=sys.stderr)
        if status in (401, 403):
            print("Check region/clientId/clientSecret -> run: {} init".format(command_name()), file=sys.stderr)

    print("Server response:\n" + format_body(text), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(130)
