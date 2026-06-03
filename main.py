from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.discord_webhook import DiscordWebhookClient
from src.henrik_api import HenrikApiClient
from src.rankings import RankingBuilder
from src.storage import HistoryStore, load_users


ROOT = Path(__file__).resolve().parent
USERS_PATH = ROOT / "users.json"
HISTORY_PATH = ROOT / "history.json"


def jst_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tokyo")).replace(microsecond=0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = os.environ.get("HENRIK_API_KEY", "")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    region = os.environ.get("VALORANT_REGION", "ap")
    platform = os.environ.get("VALORANT_PLATFORM", "pc")
    request_delay_seconds = float(os.environ.get("HENRIK_REQUEST_DELAY_SECONDS", "2.0"))
    max_retries = int(os.environ.get("HENRIK_MAX_RETRIES", "5"))
    rate_limit_wait_seconds = int(os.environ.get("HENRIK_RATE_LIMIT_WAIT_SECONDS", "60"))

    if not api_key:
        raise RuntimeError("HENRIK_API_KEY is required")

    users = load_users(USERS_PATH)
    history = HistoryStore(HISTORY_PATH)
    previous_snapshot = history.latest_snapshot()
    current_date = jst_now()

    client = HenrikApiClient(
        api_key=api_key,
        region=region,
        platform=platform,
        request_delay_seconds=request_delay_seconds,
        max_retries=max_retries,
        rate_limit_wait_seconds=rate_limit_wait_seconds,
    )
    builder = RankingBuilder(client)

    if previous_snapshot is None:
        snapshot, errors = builder.build_initial_snapshot(users, current_date)
        history.append_snapshot(snapshot)
        history.save()
        logging.info("Initial snapshot saved. Rankings are skipped until the next run.")
        if errors and webhook_url:
            DiscordWebhookClient(webhook_url).post_initial_snapshot_errors(snapshot.date, errors)
        return

    snapshot, errors = builder.build_weekly_snapshot(
        users=users,
        previous_date=previous_snapshot.date,
        current_date=current_date,
    )
    history.append_snapshot(snapshot)
    history.save()

    if webhook_url:
        DiscordWebhookClient(webhook_url).post_weekly_ranking(snapshot, errors)
    else:
        logging.info("DISCORD_WEBHOOK_URL is not set. Discord posting skipped.")


if __name__ == "__main__":
    main()
