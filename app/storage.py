"""재생목록을 JSON 파일로 저장/불러오기."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Playlist

APP_DIR = Path.home() / ".melon_player"
AUTOSAVE_PATH = APP_DIR / "last_playlist.json"


def save_playlist(playlist: Playlist, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(playlist.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # 저장 도중 꺼져도 기존 파일이 깨지지 않게


def load_playlist(path: Path | str) -> Playlist:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Playlist.from_dict(data)
