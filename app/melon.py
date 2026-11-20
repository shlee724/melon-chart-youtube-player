"""멜론 TOP 100 차트 가져오기.

- fetch_chart_html(): 네트워크 요청 (User-Agent 없으면 멜론이 406을 돌려준다)
- parse_chart(html): HTML → Song 목록 (네트워크 없이 테스트 가능)

멜론 페이지 구조가 바뀌면 parse_chart의 CSS 선택자만 고치면 된다.
단독 실행:  python -m app.melon   (상위 10곡 출력)
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .models import Song

CHART_URL = "https://www.melon.com/chart/index.htm"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


class MelonError(RuntimeError):
    pass


def fetch_chart_html(timeout: float = 10.0) -> str:
    try:
        resp = requests.get(CHART_URL, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise MelonError(f"멜론 차트 요청 실패: {e}") from e
    return resp.text


def _texts(nodes) -> list[str]:
    """중복 제거하면서 순서 유지."""
    seen, out = set(), []
    for n in nodes:
        t = n.get_text(strip=True)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def parse_chart(html: str) -> list[Song]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.lst50, tr.lst100")
    songs: list[Song] = []

    for idx, row in enumerate(rows, start=1):
        title_el = row.select_one("div.ellipsis.rank01 a") or row.select_one(
            "div.ellipsis.rank01 span"
        )
        if title_el is None:
            continue

        # 아티스트: rank02 안에 같은 이름이 두 번(보이는 것/숨김) 들어있어서 중복 제거
        artist_nodes = row.select("div.ellipsis.rank02 span.checkEllipsis a") or row.select(
            "div.ellipsis.rank02 a"
        )
        album_el = row.select_one("div.ellipsis.rank03 a")
        rank_el = row.select_one("span.rank")

        try:
            rank = int(rank_el.get_text(strip=True)) if rank_el else idx
        except ValueError:
            rank = idx

        songs.append(
            Song(
                title=title_el.get_text(strip=True),
                artist=", ".join(_texts(artist_nodes)),
                album=album_el.get_text(strip=True) if album_el else "",
                rank=rank,
                melon_id=row.get("data-song-no"),
            )
        )

    if not songs:
        raise MelonError("차트에서 곡을 찾지 못했습니다. 멜론 페이지 구조가 바뀌었을 수 있습니다.")
    return songs


def fetch_chart() -> list[Song]:
    return parse_chart(fetch_chart_html())


if __name__ == "__main__":
    for s in fetch_chart()[:10]:
        print(f"{s.rank:>3}. {s.display}  [{s.album}]")
