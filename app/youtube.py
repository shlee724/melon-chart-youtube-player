"""'아티스트 제목' → 유튜브 영상 ID 검색.

yt-dlp의 검색 기능만 사용한다(영상 다운로드는 하지 않음). API 키가 필요 없다.
나중에 YouTube Data API로 바꾸고 싶으면 search_video_id()만 교체하면 된다.

단독 실행:  python -m app.youtube "아이유 좋은 날"
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp


@dataclass
class SearchResult:
    video_id: str
    title: str
    channel: str
    duration: Optional[float]


def search(query: str, limit: int = 5) -> list[SearchResult]:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,  # 목록 정보만 (빠름)
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    results = []
    for e in info.get("entries") or []:
        if not e or not e.get("id"):
            continue
        results.append(
            SearchResult(
                video_id=e["id"],
                title=e.get("title") or "",
                channel=e.get("channel") or e.get("uploader") or "",
                duration=e.get("duration"),
            )
        )
    return results


def pick_best(results: list[SearchResult]) -> Optional[SearchResult]:
    """검색 결과 중 노래로 적당한 것을 고른다.

    지금은 단순 규칙: 10분 넘는 영상(모음집/라이브 풀영상)은 제외하고 첫 번째.
    TODO(ROADMAP): 'Topic' 채널·공식 MV 우선, 'cover'/'reaction' 제외 등 점수화.
    """
    for r in results:
        if r.duration is None or r.duration <= 600:
            return r
    return results[0] if results else None


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(text: str) -> Optional[str]:
    """사용자가 붙여넣은 유튜브 주소나 ID에서 11자리 영상 ID를 꺼낸다."""
    text = text.strip()
    if _ID_RE.match(text):
        return text
    try:
        u = urlparse(text)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    candidate = None
    if host.endswith("youtu.be"):
        candidate = u.path.lstrip("/").split("/")[0]
    elif "youtube.com" in host:
        if u.path == "/watch":
            candidate = parse_qs(u.query).get("v", [None])[0]
        elif u.path.startswith(("/embed/", "/shorts/", "/live/")):
            candidate = u.path.split("/")[2]
    return candidate if candidate and _ID_RE.match(candidate) else None


def search_video_id(query: str) -> Optional[str]:
    best = pick_best(search(query))
    return best.video_id if best else None


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "아이유 좋은 날"
    for r in search(q):
        print(r)
