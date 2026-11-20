# 멜론 TOP100 유튜브 플레이어

멜론 차트 TOP100을 가져와 재생목록을 만들고, 자유롭게 편집한 뒤, 한 곡씩 유튜브로 재생하는 파이썬 데스크톱 앱입니다.

```
┌ 툴바: [멜론 TOP100 불러오기] [열기] [저장] [유튜브 미리 검색] ─────────┐
│ 순위 제목        아티스트  앨범   유튜브 │                          │
│ 1   노래 A       가수 A   …      ✓      │    (유튜브 플레이어)      │
│ 2   노래 B       가수 B   …             │                          │
│ …  (드래그로 순서 변경)                │ ♪ 노래 A - 가수 A        │
│ [추가][수정][삭제][▲][▼][섞기]           │ [⏮][▶][⏭]   볼륨 ──●──  │
└─────────────────────────────────────────────────────────────────────┘
```

## 1. 설치 (Windows 기준)

1. [python.org](https://www.python.org/downloads/)에서 Python 3.11 이상 설치 (설치 화면에서 **Add python.exe to PATH** 체크)
2. 이 폴더에서 터미널(PowerShell)을 열고:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   (macOS/Linux는 `source .venv/bin/activate`)
3. 실행:
   ```powershell
   python main.py
   ```

> 편집기는 Android Studio보다 **PyCharm Community**나 **VS Code**(Python 확장)가 파이썬에 훨씬 편합니다. Android Studio도 같은 JetBrains 계열이라 PyCharm 화면이 익숙할 거예요.

## 2. 사용법
- **멜론 TOP100 불러오기** → 100곡이 목록에 들어옵니다.
- 곡을 **더블클릭**하면 재생. 끝나면 자동으로 다음 곡.
- 처음 재생하는 곡은 유튜브 검색에 1~3초 걸립니다. **유튜브 미리 검색**을 누르면 전체를 미리 찾아둡니다.
- 엉뚱한 영상이 나오면 **수정(F2)** → 유튜브 칸에 원하는 영상 주소를 붙여넣기.
- 유튜브 칸 `✕` = 퍼가기 금지 등으로 재생할 수 없는 곡 (자동으로 건너뜀).
- 창을 닫으면 자동 저장되고, 다음 실행 때 그대로 복원됩니다.

## 3. 테스트
```bash
pytest                                   # 핵심 로직 테스트
python -m app.melon                      # 멜론 차트 파싱 확인
python -m app.youtube "아이유 좋은 날"    # 유튜브 검색 확인
```

## 4. Claude Code로 이어서 개발하기
```bash
cd melon_player
claude
```
Claude Code는 시작할 때 `CLAUDE.md`를 자동으로 읽어서 프로젝트 구조와 규칙을 압니다. 다음 할 일은 `docs/ROADMAP.md`에 프롬프트와 함께 정리되어 있어요. 첫 요청으로 이걸 추천합니다:

> `python -m app.melon 을 실행해서 결과를 확인해줘. 곡이 100개 안 나오면 parse_chart 선택자를 고쳐줘.`

## 5. 알아둘 점
- **개인 학습용**으로 만드세요. 멜론 페이지를 자동으로 반복 요청하거나 이 앱을 배포/판매하는 건 멜론·유튜브 약관 문제가 생길 수 있습니다.
- 유튜브는 공식 임베드 플레이어로만 재생합니다(광고가 나올 수 있음). 영상 다운로드 기능은 넣지 않습니다.
- 멜론이나 유튜브 사이트가 바뀌면 일부 기능이 갑자기 안 될 수 있어요. 그럴 땐 `pip install -U yt-dlp`, 그래도 안 되면 Claude Code에게 오류 메시지를 보여주세요.
