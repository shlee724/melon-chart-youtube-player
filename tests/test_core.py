"""네트워크·GUI 없이 돌아가는 핵심 로직 테스트.  실행: pytest"""
from pathlib import Path

import pytest

from app.melon import MelonError, parse_chart
from app.models import Playlist, Song
from app.storage import load_playlist, save_playlist
from app.youtube import SearchResult, extract_video_id, pick_best

FIXTURE = Path(__file__).parent / "fixtures" / "melon_chart_sample.html"


# ---------- 멜론 파서 ----------
def test_parse_chart_reads_rows():
    songs = parse_chart(FIXTURE.read_text(encoding="utf-8"))
    assert [s.rank for s in songs] == [1, 2, 51]
    assert songs[0].title == "첫번째 노래"
    assert songs[0].artist == "가수A"          # 숨김 span 때문에 중복되지 않아야 함
    assert songs[0].album == "앨범1"
    assert songs[0].melon_id == "10000001"
    assert songs[1].artist == "가수B, 가수C"


def test_parse_chart_empty_raises():
    with pytest.raises(MelonError):
        parse_chart("<html><body>점검 중</body></html>")


# ---------- 재생목록 ----------
def _pl(n=4):
    return Playlist(songs=[Song(title=f"t{i}", artist="a") for i in range(n)])


def test_move_and_remove():
    pl = _pl()
    pl.move(0, 2)
    assert [s.title for s in pl.songs] == ["t1", "t2", "t0", "t3"]
    pl.remove(0)
    assert len(pl) == 3


def test_next_skips_unplayable_and_stops_at_end():
    pl = _pl()
    pl.songs[1].unplayable = True
    assert pl.next_index(0) == 2
    assert pl.next_index(3) is None
    assert pl.next_index(3, repeat=True) == 0
    assert pl.prev_index(2) == 0


def test_save_and_load_roundtrip(tmp_path):
    pl = _pl(2)
    pl.songs[0].video_id = "dQw4w9WgXcQ"
    path = tmp_path / "p.json"
    save_playlist(pl, path)
    loaded = load_playlist(path)
    assert loaded.songs[0].video_id == "dQw4w9WgXcQ"
    assert [s.title for s in loaded.songs] == ["t0", "t1"]


# ---------- 유튜브 ----------
@pytest.mark.parametrize("text", [
    "dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=abc",
    "https://youtu.be/dQw4w9WgXcQ?si=xyz",
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
])
def test_extract_video_id(text):
    assert extract_video_id(text) == "dQw4w9WgXcQ"


def test_extract_video_id_rejects_garbage():
    assert extract_video_id("hello world") is None
    assert extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ") is None


def test_pick_best_skips_long_videos():
    rs = [SearchResult("a" * 11, "1시간 모음", "c", 3600), SearchResult("b" * 11, "MV", "c", 210)]
    assert pick_best(rs).video_id == "b" * 11
