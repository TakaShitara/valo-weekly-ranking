from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from src.models import MatchSummary, User


class HenrikApiError(RuntimeError):
    pass


class HenrikApiClient:
    def __init__(
        self,
        api_key: str,
        region: str = "ap",
        platform: str = "pc",
        base_url: str = "https://api.henrikdev.xyz",
        timeout: int = 30,
        request_delay_seconds: float = 2.0,
        max_retries: int = 5,
        rate_limit_wait_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.platform = platform
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.request_delay_seconds = request_delay_seconds
        self.max_retries = max_retries
        self.rate_limit_wait_seconds = rate_limit_wait_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": api_key,
                "Accept": "application/json",
                "User-Agent": "valorant-weekly-ranking-batch/1.0",
            }
        )

    def rr_gain(self, user: User, since: datetime, until: datetime) -> int:
        data = self._get(
            f"/valorant/v2/mmr-history/{self.region}/{self.platform}/"
            f"{quote(user.riot_name)}/{quote(user.riot_tag)}"
        )
        entries = self._extract_data_list(data)
        total = 0
        for entry in entries:
            played_at = self._parse_mmr_datetime(entry)
            if played_at is None or not (since < played_at <= until):
                continue
            total += self._extract_rr_change(entry)
        return total

    def competitive_matches(self, user: User, since: datetime, until: datetime) -> list[MatchSummary]:
        summaries: list[MatchSummary] = []
        seen_match_ids: set[str] = set()
        start = 0

        while True:
            data = self._get(
                f"/valorant/v4/matches/{self.region}/{self.platform}/"
                f"{quote(user.riot_name)}/{quote(user.riot_tag)}",
                params={"mode": "competitive", "size": 10, "start": start},
            )
            matches = self._extract_data_list(data)
            if not matches:
                break

            should_continue = False
            for match in matches:
                started_at = self._parse_match_datetime(match)
                if started_at is None:
                    continue
                if started_at <= since:
                    continue
                should_continue = True
                if started_at > until:
                    continue

                summary = self._to_match_summary(user, match, started_at)
                if summary.match_id in seen_match_ids:
                    continue
                seen_match_ids.add(summary.match_id)
                summaries.append(summary)

            if not should_continue or len(matches) < 10:
                break
            start += 10

        return summaries

    def ping_player(self, user: User) -> None:
        self._get(
            f"/valorant/v2/mmr-history/{self.region}/{self.platform}/"
            f"{quote(user.riot_name)}/{quote(user.riot_tag)}"
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(1, self.max_retries + 1):
            if self.request_delay_seconds > 0:
                time.sleep(self.request_delay_seconds)

            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=self.timeout,
            )

            if response.status_code != 429:
                break

            wait_seconds = self._retry_after_seconds(response) or self.rate_limit_wait_seconds
            logging.warning(
                "HenrikDev rate limit hit. Waiting %s seconds before retry %s/%s.",
                wait_seconds,
                attempt,
                self.max_retries,
            )
            time.sleep(wait_seconds)
        else:
            raise HenrikApiError("Rate limit exceeded")

        if response.status_code == 429:
            raise HenrikApiError("Rate limit exceeded")
        if response.status_code >= 400:
            raise HenrikApiError(self._error_message(response))
        payload = response.json()
        status = int(payload.get("status", response.status_code))
        if status >= 400:
            raise HenrikApiError(str(payload.get("message") or payload.get("details") or status))
        return payload

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(1, int(value))
        except ValueError:
            return None

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or f"HTTP {response.status_code}"
        return str(
            payload.get("message")
            or payload.get("details")
            or payload.get("errors")
            or f"HTTP {response.status_code}"
        )

    @staticmethod
    def _extract_data_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    @staticmethod
    def _parse_mmr_datetime(entry: dict[str, Any]) -> datetime | None:
        raw_timestamp = entry.get("date_raw")
        if isinstance(raw_timestamp, int | float):
            return datetime.fromtimestamp(raw_timestamp, timezone.utc)

        for key in ("date", "started_at"):
            value = entry.get(key)
            parsed = parse_datetime(value)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_match_datetime(match: dict[str, Any]) -> datetime | None:
        metadata = match.get("metadata", {})
        for key in ("started_at", "game_start"):
            value = metadata.get(key)
            if isinstance(value, int | float):
                return datetime.fromtimestamp(value, timezone.utc)
            parsed = parse_datetime(value)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _extract_rr_change(entry: dict[str, Any]) -> int:
        for key in ("rr_change", "mmr_change_to_last_game", "change", "last_change"):
            value = entry.get(key)
            if isinstance(value, int):
                return value
        return 0

    def _to_match_summary(self, user: User, match: dict[str, Any], started_at: datetime) -> MatchSummary:
        match_id = self._match_id(match)
        players = self._players(match)
        target = self._target_player(user, players)
        if target is None:
            raise HenrikApiError("Player was not found in match data")

        team_id = str(target.get("team_id") or target.get("team") or "")
        won = self._team_won(match, team_id)
        score = self._player_score(target)
        top_score = max((self._player_score(player) for player in players), default=score)
        return MatchSummary(
            match_id=match_id,
            started_at=started_at,
            won=won,
            score=score,
            top_score=top_score,
        )

    @staticmethod
    def _match_id(match: dict[str, Any]) -> str:
        metadata = match.get("metadata", {})
        return str(metadata.get("match_id") or metadata.get("matchid") or "")

    @staticmethod
    def _players(match: dict[str, Any]) -> list[dict[str, Any]]:
        players = match.get("players", [])
        if isinstance(players, list):
            return players
        if isinstance(players, dict):
            all_players = players.get("all_players", [])
            return all_players if isinstance(all_players, list) else []
        return []

    @staticmethod
    def _target_player(user: User, players: list[dict[str, Any]]) -> dict[str, Any] | None:
        riot_name = user.riot_name.casefold()
        riot_tag = user.riot_tag.casefold()
        for player in players:
            name = str(player.get("name", "")).casefold()
            tag = str(player.get("tag", "")).casefold()
            if name == riot_name and tag == riot_tag:
                return player
        return None

    @staticmethod
    def _player_score(player: dict[str, Any]) -> int:
        stats = player.get("stats", {})
        if isinstance(stats, dict) and isinstance(stats.get("score"), int):
            return int(stats["score"])
        if isinstance(player.get("score"), int):
            return int(player["score"])
        return 0

    @staticmethod
    def _team_won(match: dict[str, Any], team_id: str) -> bool:
        teams = match.get("teams", {})
        team_key = team_id.casefold()
        if isinstance(teams, list):
            for team in teams:
                if str(team.get("team_id") or team.get("team")).casefold() == team_key:
                    return bool(team.get("won") or team.get("has_won"))
        if isinstance(teams, dict):
            team = teams.get(team_key) or teams.get(team_key.capitalize()) or teams.get(team_id)
            if isinstance(team, dict):
                return bool(team.get("won") or team.get("has_won"))
        return False


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
