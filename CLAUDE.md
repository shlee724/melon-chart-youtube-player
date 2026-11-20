# CLAUDE.md — 이 프로젝트에서 Claude Code가 지켜야 할 것

## 프로젝트 한 줄 요약
멜론 TOP100 차트를 긁어와 재생목록을 만들고, 사용자가 GUI에서 편집한 뒤, 각 곡을 유튜브 임베드 플레이어로 차례로 재생하는 데스크톱 앱 (Python + PySide6).

## 사용자 정보
- 한국어로 대화한다. 코드 주석·UI 문구도 한국어.
- 사용자는 비전공 대학생이다. 변경할 때마다 **무엇을, 왜** 바꿨는지 쉬운 말로 짧게 설명하고, 새 개념(시그널/슬롯, 스레드 등)은 한두 문장으로 풀어준다.
- 한 번에 큰 변경을 하지 말고, 기능 하나씩 작게 나눠 진행한다.

## 실행 / 테스트
```bash
pip install -r requirements.txt
python main.py          # 앱 실행
pytest                  # 테스트 (네트워크·GUI 없이 돌아감)
python -m app.melon     # 멜론 차트 파싱만 확인 (상위 10곡 출력)
python -m app.youtube "아이유 좋은 날"   # 유튜브 검색만 확인
```
코드를 바꾼 뒤에는 항상 `pytest`를 돌려 통과를 확인한다.

## 구조
```
main.py               앱 시작점
app/models.py         Song, Playlist (순수 파이썬, GUI 의존 없음)
app/melon.py          멜론 차트 요청 + HTML 파싱 (parse_chart는 네트워크 없이 테스트 가능)
app/youtube.py        yt-dlp로 '검색만' 해서 영상 ID 얻기, 주소→ID 변환
app/storage.py        재생목록 JSON 저장/불러오기 (~/.melon_player/last_playlist.json 자동저장)
app/workers.py        run_async(): 네트워크 작업을 백그라운드 스레드로
app/player.py         QWebEngineView + 유튜브 IFrame API 플레이어 위젯
app/main_window.py    메인 창 (재생목록 트리 + 플레이어 + 버튼)
tests/                pytest 테스트, fixtures/에 멜론 HTML 샘플
docs/ROADMAP.md       다음에 할 일 목록
```

## 반드시 지킬 규칙
1. **GUI 스레드에서 네트워크 요청 금지.** 멜론·유튜브 요청은 항상 `run_async()`로.
2. **로직은 models/melon/youtube/storage에, 화면 코드는 main_window에.** 새 로직은 GUI 없이 테스트할 수 있게 만들고 tests/에 테스트를 추가한다.
3. **유튜브는 공식 임베드 플레이어로만 재생한다.** yt-dlp로 음원/영상을 다운로드하거나 스트림 주소를 뽑아 직접 재생하는 기능은 만들지 않는다(유튜브 약관 위반). yt-dlp는 검색 용도로만.
4. 플레이어 페이지는 반드시 `http://127.0.0.1:포트`로 띄운다. `setHtml()`이나 `file://`로 바꾸면 Referer가 없어 유튜브가 Error 153을 낸다.
5. **멜론 요청은 사용자가 버튼을 눌렀을 때만**, 한 번에 한 번. 자동 반복 크롤링·짧은 주기 새로고침은 넣지 않는다.
6. 멜론 HTML 구조가 바뀌면 `parse_chart()`의 CSS 선택자만 고치고, `tests/fixtures/melon_chart_sample.html`도 실제 구조에 맞게 갱신한다.
7. 재생 중인 곡은 인덱스가 아니라 `Song` 객체(`self.current`)로 추적한다 — 드래그로 순서를 바꿔도 안전하도록. `Song`은 `eq=False`라 `is`로 비교한다.

## 자주 생기는 문제
- 멜론 406 오류 → `HEADERS`의 User-Agent 확인.
- 유튜브 검색 실패 → `pip install -U yt-dlp` (유튜브가 자주 바뀌어서 yt-dlp도 자주 업데이트됨).
- 오류 101/150 → 해당 영상이 퍼가기 금지. 앱이 자동으로 건너뜀 (ROADMAP: 다른 검색 결과로 재시도).
- 리눅스에서 QtWebEngine이 안 뜨면 `QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox"`.
