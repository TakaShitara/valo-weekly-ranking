from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from src.models import FetchError, PlayerStats, Snapshot
from src.rankings import top_matches, top_mvp, top_rr, top_win_rate


class DiscordWebhookClient:
    def __init__(self, webhook_url: str, timeout: int = 30) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    def post_weekly_ranking(
        self,
        snapshot: Snapshot,
        previous_date: datetime,
        errors: list[FetchError],
    ) -> None:
        payload = {
            "embeds": [
                {
                    "title": "TR週間ランキング",
                    "description": (
                        "集計期間\n"
                        f"{format_date(previous_date)} 〜 {format_date(snapshot.date)}"
                    ),
                    "color": 0xFF4655,
                    "fields": [
                        {
                            "name": "RR増加ランキング TOP3",
                            "value": format_rr(top_rr(snapshot.players)),
                            "inline": False,
                        },
                        {
                            "name": "\nMVPランキング TOP3",
                            "value": format_mvp(top_mvp(snapshot.players)),
                            "inline": False,
                        },
                        {
                            "name": "\n勝率ランキング TOP3",
                            "value": format_win_rate(top_win_rate(snapshot.players)),
                            "inline": False,
                        },
                        {
                            "name": "\n試合数ランキング TOP3",
                            "value": format_matches(top_matches(snapshot.players)),
                            "inline": False,
                        },
                        {
                            "name": "\nエラー",
                            "value": format_errors(errors),
                            "inline": False,
                        },
                    ],
                }
            ]
        }
        self._post(payload)

    def post_initial_snapshot_errors(self, date: datetime, errors: list[FetchError]) -> None:
        payload = {
            "embeds": [
                {
                    "title": "VALORANT 週間ランキング 初回スナップショット",
                    "description": f"集計日時: {format_date(date)}\nランキング生成は次回から行います。",
                    "color": 0xFF4655,
                    "fields": [{"name": "エラー", "value": format_errors(errors), "inline": False}],
                }
            ]
        }
        self._post(payload)

    def _post(self, payload: dict[str, Any]) -> None:
        response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
        response.raise_for_status()


def format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def format_rr(players: list[PlayerStats]) -> str:
    if not players:
        return "対象者なし"
    return "\n".join(
        f"{rank_icon(index)} **{player.name}**\n{player.rr_gain:+} RR"
        for index, player in enumerate(players, start=1)
    )


def format_mvp(players: list[PlayerStats]) -> str:
    if not players:
        return "対象者なし"
    return "\n".join(
        f"{rank_icon(index)} **{player.name}**\n{player.mvp}回"
        for index, player in enumerate(players, start=1)
    )


def format_win_rate(players: list[PlayerStats]) -> str:
    if not players:
        return "対象者なし（5試合以上）"
    return "\n".join(
        f"{rank_icon(index)} **{player.name}**\n"
        f"{player.win_rate:.1%} / {player.wins}勝 {player.losses}敗 / {player.matches}試合"
        for index, player in enumerate(players, start=1)
    )


def format_matches(players: list[PlayerStats]) -> str:
    if not players:
        return "対象者なし"
    return "\n".join(
        f"{rank_icon(index)} **{player.name}**\n"
        f"{player.matches}試合 / {player.wins}勝 {player.losses}敗"
        for index, player in enumerate(players, start=1)
    )


def format_errors(errors: list[FetchError]) -> str:
    if not errors:
        return "✅ エラーなし"
    lines = ["⚠️ 集計エラー"]
    for error in errors:
        lines.append("")
        lines.append(error.player_name)
        lines.append(error.message)
    return "\n".join(lines)


def rank_icon(index: int) -> str:
    icons = {
        1: "🥇",
        2: "🥈",
        3: "🥉",
    }
    return icons.get(index, f"{index}.")
