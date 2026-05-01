import json
import logging
import os
import time
from decimal import Decimal
from pathlib import Path

import requests
from requests.auth import HTTPDigestAuth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("monero-bot")

RPC_HOST = os.getenv("RPC_HOST", "monero-wallet-rpc")
RPC_PORT = int(os.getenv("RPC_PORT", "18082"))
RPC_USER = os.getenv("RPC_USER", "")
RPC_PASS = os.getenv("RPC_PASS", "")
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "900"))
STATE_FILE = Path(os.getenv("STATE_FILE", "/app/data/state.json"))
WALLET_LABEL = os.getenv("WALLET_LABEL", "Monero Wallet")

ATOMIC = Decimal("1000000000000")
RPC_URL = f"http://{RPC_HOST}:{RPC_PORT}/json_rpc"


def rpc(method: str, params: dict | None = None) -> dict:
    auth = HTTPDigestAuth(RPC_USER, RPC_PASS) if RPC_USER else None
    r = requests.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}},
        auth=auth,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def to_xmr(atomic: int) -> Decimal:
    return Decimal(atomic) / ATOMIC


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"balance": None, "unlocked": None}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def post_discord(balance: int, unlocked: int, prev_balance: int | None) -> None:
    bal_xmr = to_xmr(balance)
    unl_xmr = to_xmr(unlocked)

    if prev_balance is None:
        title = f"{WALLET_LABEL} – Initial Balance"
        delta_line = ""
    else:
        delta = to_xmr(balance - prev_balance)
        sign = "+" if delta >= 0 else ""
        title = f"{WALLET_LABEL} – Balance Changed"
        delta_line = f"\n**Change:** {sign}{delta:.12f} XMR"

    description = (
        f"**Total:** {bal_xmr:.12f} XMR\n"
        f"**Available:** {unl_xmr:.12f} XMR"
        f"{delta_line}"
    )
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0xF26822,
            }
        ]
    }
    r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    r.raise_for_status()


def wait_for_rpc() -> None:
    for _ in range(60):
        try:
            rpc("get_version")
            log.info("Wallet-RPC reachable")
            return
        except Exception as e:
            log.info("Waiting for wallet-rpc... (%s)", e)
            time.sleep(5)
    raise SystemExit("wallet-rpc not reachable after 5 minutes")


def main() -> None:
    wait_for_rpc()
    state = load_state()
    log.info("Starting polling every %s seconds", INTERVAL)

    while True:
        try:
            try:
                rpc("refresh")
            except Exception as e:
                log.warning("refresh failed: %s", e)

            res = rpc("get_balance")
            balance = res["balance"]
            unlocked = res["unlocked_balance"]

            if state["balance"] != balance:
                log.info(
                    "Balance change: %s -> %s atomic units",
                    state["balance"],
                    balance,
                )
                post_discord(balance, unlocked, state["balance"])
                state = {"balance": balance, "unlocked": unlocked}
                save_state(state)
            else:
                log.info("No change (%s XMR)", to_xmr(balance))
        except Exception:
            log.exception("Check failed")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
