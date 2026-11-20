"""데이터 모델: 노래(Song)와 재생목록(Playlist).

GUI와 분리된 순수 파이썬 코드라서 테스트하기 쉽다.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(eq=False)  # 같은 제목·가수라도 서로 다른 항목으로 취급 (객체 동일성으로 비교)
class Song:
    title: str
    artist: str
    album: str = ""
    rank: Optional[int] = None        # 멜론 차트 순위 (직접 추가한 곡은 None)
    melon_id: Optional[str] = None    # 멜론 곡 번호 (data-song-no)
    video_id: Optional[str] = None    # 유튜브 영상 ID (검색 후 채워짐)
    unplayable: bool = False          # 임베드 불가 등으로 재생 실패한 곡

    @property
    def search_query(self) -> str:
        """유튜브 검색어. 공식 음원이 잘 걸리도록 '아티스트 제목' 형태."""
        return f"{self.artist} {self.title}"

    @property
    def display(self) -> str:
        return f"{self.title} - {self.artist}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Song":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Playlist:
    name: str = "새 재생목록"
    songs: list[Song] = field(default_factory=list)

    # ---- 편집 ----
    def add(self, song: Song, index: Optional[int] = None) -> None:
        if index is None:
            self.songs.append(song)
        else:
            self.songs.insert(index, song)

    def remove(self, index: int) -> Song:
        return self.songs.pop(index)

    def move(self, src: int, dst: int) -> None:
        """src 위치의 곡을 dst 위치로 옮긴다."""
        song = self.songs.pop(src)
        self.songs.insert(dst, song)

    def shuffle(self) -> None:
        random.shuffle(self.songs)

    # ---- 재생 순서 ----
    def next_index(self, current: int, repeat: bool = False) -> Optional[int]:
        """다음에 재생할 곡의 인덱스. 재생 불가 곡은 건너뛴다."""
        n = len(self.songs)
        for step in range(1, n + 1):
            i = current + step
            if i >= n:
                if not repeat:
                    return None
                i %= n
            if not self.songs[i].unplayable:
                return i
        return None

    def prev_index(self, current: int) -> Optional[int]:
        for i in range(current - 1, -1, -1):
            if not self.songs[i].unplayable:
                return i
        return None

    # ---- 직렬화 ----
    def to_dict(self) -> dict:
        return {"name": self.name, "songs": [s.to_dict() for s in self.songs]}

    @classmethod
    def from_dict(cls, data: dict) -> "Playlist":
        return cls(
            name=data.get("name", "재생목록"),
            songs=[Song.from_dict(s) for s in data.get("songs", [])],
        )

    def __len__(self) -> int:
        return len(self.songs)
