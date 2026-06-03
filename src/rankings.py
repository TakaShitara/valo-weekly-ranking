from __future__ import annotations

import logging
from datetime import datetime

from src.henrik_api import HenrikApiClient
from src.models import FetchError, PlayerStats, Snapshot, User


class RankingBuilder:
    def __init__(self, api_client: HenrikApiClient) -> None:
        self.api_client = api_client

    def build_initial_snapshot(
        self,
        users: list[User],
        current_date: datetime,
    ) -> tuple[Snapshot, list[FetchError]]:
        players: list[PlayerStats] = []
        errors: list[FetchError] = []

        for user in users:
            try:
                self.api_client.ping_player(user)
                players.append(PlayerStats(name=user.name))
                logging.info("Initial check succeeded for %s", user.name)
            except Exception as exc:
                errors.append(FetchError(user.name, str(exc)))
                logging.warning("Initial check failed for %s: %s", user.name, exc)

        return Snapshot(date=current_date, players=players), errors

    def build_weekly_snapshot(
        self,
        users: list[User],
        previous_date: datetime,
        current_date: datetime,
    ) -> tuple[Snapshot, list[FetchError]]:
        players: list[PlayerStats] = []
        errors: list[FetchError] = []

        for user in users:
            try:
                matches = self.api_client.competitive_matches(user, previous_date, current_date)
                rr_gain = self.api_client.rr_gain(user, previous_date, current_date)
                wins = sum(1 for match in matches if match.won)
                losses = sum(1 for match in matches if not match.won)
                mvp = sum(1 for match in matches if match.score == match.top_score)
                players.append(
                    PlayerStats(
                        name=user.name,
                        rr_gain=rr_gain,
                        wins=wins,
                        losses=losses,
                        matches=len(matches),
                        mvp=mvp,
                    )
                )
                logging.info("Aggregated %s: matches=%s rr=%s", user.name, len(matches), rr_gain)
            except Exception as exc:
                errors.append(FetchError(user.name, str(exc)))
                logging.warning("Skipped %s: %s", user.name, exc)

        return Snapshot(date=current_date, players=players), errors


def top_rr(players: list[PlayerStats], limit: int = 3) -> list[PlayerStats]:
    return sorted(players, key=lambda player: (player.rr_gain, player.wins), reverse=True)[:limit]


def top_mvp(players: list[PlayerStats], limit: int = 3) -> list[PlayerStats]:
    return sorted(players, key=lambda player: (player.mvp, player.matches), reverse=True)[:limit]


def top_win_rate(players: list[PlayerStats], limit: int = 3) -> list[PlayerStats]:
    eligible = [player for player in players if player.matches >= 5]
    return sorted(eligible, key=lambda player: (player.win_rate, player.wins), reverse=True)[:limit]


def top_matches(players: list[PlayerStats], limit: int = 3) -> list[PlayerStats]:
    return sorted(players, key=lambda player: (player.matches, player.wins), reverse=True)[:limit]
