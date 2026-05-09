from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCOPES = "offline_access User.Read Files.ReadWrite Calendars.ReadWrite"


def main() -> int:
    args = parse_args()
    token_base = f"https://login.microsoftonline.com/{args.tenant}/oauth2/v2.0"
    device = post_form(
        f"{token_base}/devicecode",
        {
            "client_id": args.client_id,
            "scope": SCOPES,
        },
    )
    print(device["message"])
    print("Waiting for Microsoft sign-in and consent...")

    while True:
        time.sleep(int(device.get("interval", 5)))
        try:
            token = post_form(
                f"{token_base}/token",
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": args.client_id,
                    "device_code": device["device_code"],
                },
            )
            break
        except RuntimeError as exc:
            payload = json.loads(str(exc))
            if payload.get("error") in {"authorization_pending", "slow_down"}:
                continue
            raise

    lines = [
        f"MS_GRAPH_TENANT_ID={args.tenant}",
        f"MS_GRAPH_CLIENT_ID={args.client_id}",
        "MS_GRAPH_CLIENT_SECRET=",
        f"MS_GRAPH_REFRESH_TOKEN={token['refresh_token']}",
        "",
    ]
    args.env_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.env_file}")
    print("Next: source the env file, then run python3 -m etl.local_board_meetings.runner --live --limit 3")
    return 0


def post_form(url: str, values: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(values).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Microsoft Graph refresh-token env values using device-code auth.")
    parser.add_argument("--client-id", required=True, help="Azure app registration Application (client) ID.")
    parser.add_argument("--tenant", default="common", help="Tenant ID, domain, or common.")
    parser.add_argument("--env-file", type=Path, default=Path(".env.local-board-meetings"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
