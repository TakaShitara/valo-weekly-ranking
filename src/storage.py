from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import Snapshot, User


def load_users(path: Path) -> list[User]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    users: list[User] = []
    for item in data.get("users", []):
        users.append(
            User(
                name=str(item["name"]),
                riot_name=str(item["riot_name"]),
                riot_tag=str(item["riot_tag"]),
            )
        )
    return users


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"snapshots": []}
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def snapshots(self) -> list[Snapshot]:
        return [Snapshot.from_json(item) for item in self._data.get("snapshots", [])]

    def latest_snapshot(self) -> Snapshot | None:
        snapshots = self.snapshots()
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.date)

    def append_snapshot(self, snapshot: Snapshot) -> None:
        self._data.setdefault("snapshots", []).append(snapshot.to_json())

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)
            file.write("\n")
