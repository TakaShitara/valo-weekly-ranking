from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class User:
    name: str
    riot_name: str
    riot_tag: str


@dataclass
class PlayerStats:
    name: str
    rr_gain: int = 0
    wins: int = 0
    losses: int = 0
    matches: int = 0
    mvp: int = 0

    @property
    def win_rate(self) -> float:
        if self.matches == 0:
            return 0.0
        return self.wins / self.matches

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rr_gain": self.rr_gain,
            "wins": self.wins,
            "losses": self.losses,
            "matches": self.matches,
            "mvp": self.mvp,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "PlayerStats":
        return cls(
            name=str(data["name"]),
            rr_gain=int(data.get("rr_gain", 0)),
            wins=int(data.get("wins", 0)),
            losses=int(data.get("losses", 0)),
            matches=int(data.get("matches", 0)),
            mvp=int(data.get("mvp", 0)),
        )


@dataclass
class Snapshot:
    date: datetime
    players: list[PlayerStats]

    def to_json(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "players": [player.to_json() for player in self.players],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Snapshot":
        return cls(
            date=datetime.fromisoformat(str(data["date"])),
            players=[PlayerStats.from_json(player) for player in data.get("players", [])],
        )


@dataclass
class FetchError:
    player_name: str
    message: str


@dataclass(frozen=True)
class MatchSummary:
    match_id: str
    started_at: datetime
    won: bool
    score: int
    top_score: int
