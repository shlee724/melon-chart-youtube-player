"""메인 창: 왼쪽은 재생목록(편집 가능), 오른쪽은 유튜브 플레이어."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QSlider, QSplitter, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import melon, storage, youtube
from .models import Playlist, Song
from .player import EMBED_BLOCKED_ERRORS, STATE_PLAYING, YouTubePlayer
from .workers import run_async

SONG_ROLE = Qt.ItemDataRole.UserRole
COL_RANK, COL_TITLE, COL_ARTIST, COL_ALBUM, COL_YT = range(5)


# ---------------------------------------------------------------- 곡 편집 창
class SongDialog(QDialog):
    def __init__(self, song: Optional[Song] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("곡 수정" if song else "곡 추가")
        self.title = QLineEdit(song.title if song else "")
        self.artist = QLineEdit(song.artist if song else "")
        self.album = QLineEdit(song.album if song else "")
        self.video = QLineEdit(song.video_id or "" if song else "")
        self.video.setPlaceholderText("비워두면 자동 검색 · 유튜브 주소 붙여넣기 가능")

        form = QFormLayout(self)
        form.addRow("제목*", self.title)
        form.addRow("아티스트*", self.artist)
        form.addRow("앨범", self.album)
        form.addRow("유튜브", self.video)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.resize(420, 0)

    def _validate(self):
        if not self.title.text().strip() or not self.artist.text().strip():
            QMessageBox.warning(self, "입력 필요", "제목과 아티스트는 꼭 입력해 주세요.")
            return
        if self.video.text().strip() and not youtube.extract_video_id(self.video.text()):
            QMessageBox.warning(self, "주소 오류", "유튜브 주소나 영상 ID를 알아볼 수 없습니다.")
            return
        self.accept()

    def apply_to(self, song: Song) -> None:
        song.title = self.title.text().strip()
        song.artist = self.artist.text().strip()
        song.album = self.album.text().strip()
        new_id = youtube.extract_video_id(self.video.text()) if self.video.text().strip() else None
        if new_id != song.video_id:
            song.video_id = new_id
            song.unplayable = False


# ---------------------------------------------------------------- 메인 창
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("멜론 TOP100 유튜브 플레이어")
        self.resize(1280, 720)

        self.current: Optional[Song] = None   # 지금 재생 중인 곡 (객체로 추적 → 순서를 바꿔도 안전)
        self.file_path: Optional[str] = None
        self._prefetching = False

        self._build_ui()
        self._load_autosave()

    # ---------------- UI 구성 ----------------
    def _build_ui(self):
        tb = QToolBar("메뉴")
        tb.setMovable(False)
        self.addToolBar(tb)
        self._action(tb, "멜론 TOP100 불러오기", self.load_melon_chart, "Ctrl+M")
        tb.addSeparator()
        self._action(tb, "열기", self.open_file, QKeySequence.StandardKey.Open)
        self._action(tb, "저장", self.save_file, QKeySequence.StandardKey.Save)
        self._action(tb, "다른 이름으로 저장", lambda: self.save_file(save_as=True))
        tb.addSeparator()
        self._action(tb, "유튜브 미리 검색", self.prefetch_all)

        # 왼쪽: 재생목록
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["순위", "제목", "아티스트", "앨범", "유튜브"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)  # 드래그로 순서 변경
        self.tree.itemDoubleClicked.connect(lambda item, _c: self.play(item.data(0, SONG_ROLE)))
        for col, w in [(COL_RANK, 50), (COL_TITLE, 220), (COL_ARTIST, 150), (COL_ALBUM, 140), (COL_YT, 50)]:
            self.tree.setColumnWidth(col, w)

        btns = QHBoxLayout()
        for text, slot in [("추가", self.add_song), ("수정", self.edit_song), ("삭제", self.delete_songs),
                           ("▲", lambda: self.move_selected(-1)), ("▼", lambda: self.move_selected(1)),
                           ("섞기", self.shuffle)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.tree)
        lv.addLayout(btns)

        # 오른쪽: 플레이어
        self.player = YouTubePlayer()
        self.player.ended.connect(self.play_next)
        self.player.error.connect(self._on_player_error)
        self.player.state_changed.connect(self._on_state)

        self.now_label = QLabel("재생 중인 곡 없음")
        self.now_label.setWordWrap(True)
        self.btn_prev = QPushButton("⏮ 이전")
        self.btn_play = QPushButton("▶ 재생")
        self.btn_next = QPushButton("다음 ⏭")
        self.btn_prev.clicked.connect(self.play_prev)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.play_next)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setMaximumWidth(140)
        self.volume.valueChanged.connect(self.player.set_volume)

        controls = QHBoxLayout()
        for w in (self.btn_prev, self.btn_play, self.btn_next):
            controls.addWidget(w)
        controls.addStretch()
        controls.addWidget(QLabel("볼륨"))
        controls.addWidget(self.volume)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(self.player, 1)
        rv.addWidget(self.now_label)
        rv.addLayout(controls)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([620, 660])
        self.setCentralWidget(split)

        # 단축키
        self.addAction(QAction(self, shortcut=QKeySequence(Qt.Key.Key_Delete), triggered=self.delete_songs))
        self.addAction(QAction(self, shortcut=QKeySequence("F2"), triggered=self.edit_song))
        self.addAction(QAction(self, shortcut=QKeySequence("Ctrl+Right"), triggered=self.play_next))
        self.addAction(QAction(self, shortcut=QKeySequence("Ctrl+Left"), triggered=self.play_prev))

    def _action(self, toolbar, text, slot, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        toolbar.addAction(a)
        return a

    def status(self, msg: str, ms: int = 5000):
        self.statusBar().showMessage(msg, ms)

    # ---------------- 목록 ↔ 화면 ----------------
    def _make_item(self, song: Song) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setData(0, SONG_ROLE, song)
        # ItemIsDropEnabled를 빼야 드래그 시 다른 곡 '안으로' 들어가지 않고 사이에 끼워진다
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
        self._refresh_item(item)
        return item

    def _refresh_item(self, item: QTreeWidgetItem):
        s: Song = item.data(0, SONG_ROLE)
        item.setText(COL_RANK, str(s.rank) if s.rank else "-")
        item.setText(COL_TITLE, s.title)
        item.setText(COL_ARTIST, s.artist)
        item.setText(COL_ALBUM, s.album)
        item.setText(COL_YT, "✕" if s.unplayable else ("✓" if s.video_id else ""))
        font = QFont()
        font.setBold(s is self.current)
        for c in range(self.tree.columnCount()):
            item.setFont(c, font)

    def _items(self) -> list[QTreeWidgetItem]:
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def _item_of(self, song: Song) -> Optional[QTreeWidgetItem]:
        return next((it for it in self._items() if it.data(0, SONG_ROLE) is song), None)

    def playlist(self) -> Playlist:
        """화면에 보이는 순서 그대로의 재생목록 (드래그로 바뀐 순서 포함)."""
        return Playlist(name=self.windowTitle(), songs=[it.data(0, SONG_ROLE) for it in self._items()])

    def set_songs(self, songs: list[Song], append: bool = False):
        if not append:
            self.tree.clear()
            self.current = None
        self.tree.addTopLevelItems([self._make_item(s) for s in songs])

    # ---------------- 편집 ----------------
    def add_song(self):
        dlg = SongDialog(parent=self)
        if dlg.exec():
            song = Song(title="", artist="")
            dlg.apply_to(song)
            self.tree.addTopLevelItem(self._make_item(song))

    def edit_song(self):
        item = self.tree.currentItem()
        if not item:
            return
        song = item.data(0, SONG_ROLE)
        dlg = SongDialog(song, parent=self)
        if dlg.exec():
            dlg.apply_to(song)
            self._refresh_item(item)

    def delete_songs(self):
        for item in self.tree.selectedItems():
            if item.data(0, SONG_ROLE) is self.current:
                self.current = None
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))

    def move_selected(self, delta: int):
        item = self.tree.currentItem()
        if not item:
            return
        i = self.tree.indexOfTopLevelItem(item)
        j = i + delta
        if 0 <= j < self.tree.topLevelItemCount():
            self.tree.takeTopLevelItem(i)
            self.tree.insertTopLevelItem(j, item)
            self.tree.setCurrentItem(item)

    def shuffle(self):
        pl = self.playlist()
        pl.shuffle()
        current = self.current
        self.set_songs(pl.songs)
        self.current = current
        for it in self._items():
            self._refresh_item(it)

    # ---------------- 멜론 / 파일 ----------------
    def load_melon_chart(self):
        self.status("멜론 차트를 가져오는 중...", 0)
        run_async(melon.fetch_chart, on_done=self._on_chart, on_error=self._show_error)

    def _on_chart(self, songs: list[Song]):
        append = False
        if self.tree.topLevelItemCount():
            box = QMessageBox(self)
            box.setWindowTitle("멜론 TOP100")
            box.setText(f"{len(songs)}곡을 가져왔습니다. 현재 목록을 어떻게 할까요?")
            replace = box.addButton("교체", QMessageBox.ButtonRole.AcceptRole)
            add = box.addButton("뒤에 추가", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("취소", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() not in (replace, add):
                self.status("취소했습니다.")
                return
            append = box.clickedButton() is add
        self.set_songs(songs, append=append)
        self.status(f"멜론 차트 {len(songs)}곡을 불러왔습니다.")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "재생목록 열기", "", "재생목록 (*.json)")
        if path:
            try:
                self.set_songs(storage.load_playlist(path).songs)
                self.file_path = path
                self.status(f"불러옴: {path}")
            except Exception as e:  # noqa: BLE001
                self._show_error(f"파일을 열 수 없습니다: {e}")

    def save_file(self, save_as: bool = False):
        path = self.file_path
        if save_as or not path:
            path, _ = QFileDialog.getSaveFileName(self, "재생목록 저장", "playlist.json", "재생목록 (*.json)")
            if not path:
                return
        storage.save_playlist(self.playlist(), path)
        self.file_path = path
        self.status(f"저장함: {path}")

    def _load_autosave(self):
        if storage.AUTOSAVE_PATH.exists():
            try:
                self.set_songs(storage.load_playlist(storage.AUTOSAVE_PATH).songs)
                self.status("지난번 재생목록을 불러왔습니다.")
            except Exception:  # noqa: BLE001 - 자동저장 파일이 깨졌으면 그냥 무시
                pass

    def closeEvent(self, event):  # noqa: N802
        storage.save_playlist(self.playlist(), storage.AUTOSAVE_PATH)
        self.player.shutdown()
        super().closeEvent(event)

    # ---------------- 재생 ----------------
    def play(self, song: Optional[Song]):
        if song is None:
            return
        previous, self.current = self.current, song
        for s in (previous, song):
            if s and (it := self._item_of(s)):
                self._refresh_item(it)
        if it := self._item_of(song):
            self.tree.scrollToItem(it)
        self.now_label.setText(f"♪ {song.display}")

        if song.video_id:
            self.player.play_video(song.video_id)
        else:
            self.status(f"유튜브에서 찾는 중: {song.search_query}", 0)
            run_async(youtube.search_video_id, song.search_query,
                      on_done=lambda vid, s=song: self._on_searched(s, vid, play=True),
                      on_error=lambda msg, s=song: self._on_search_failed(s, msg))

    def _on_searched(self, song: Song, video_id: Optional[str], play: bool):
        if video_id:
            song.video_id = video_id
        else:
            song.unplayable = True
        if it := self._item_of(song):
            self._refresh_item(it)
        if play and song is self.current:
            if video_id:
                self.status("재생 시작")
                self.player.play_video(video_id)
            else:
                self.status(f"검색 결과 없음 → 건너뜀: {song.display}")
                self.play_next()

    def _on_search_failed(self, song: Song, msg: str):
        self.status(f"검색 실패: {msg}")
        if song is self.current:
            song.unplayable = True
            self.play_next()

    def _neighbor(self, step: int) -> Optional[Song]:
        pl = self.playlist()
        if not pl.songs:
            return None
        if self.current is None or self.current not in pl.songs:
            return pl.songs[0]
        i = next(k for k, s in enumerate(pl.songs) if s is self.current)
        j = pl.next_index(i) if step > 0 else pl.prev_index(i)
        return pl.songs[j] if j is not None else None

    def play_next(self):
        nxt = self._neighbor(+1)
        if nxt:
            self.play(nxt)
        else:
            self.status("재생목록 끝입니다.")

    def play_prev(self):
        self.play(self._neighbor(-1))

    def toggle_play(self):
        if self.current is None:
            self.play(self._neighbor(+1))
        else:
            self.player.toggle_play()

    def _on_state(self, state: int):
        self.btn_play.setText("⏸ 일시정지" if state == STATE_PLAYING else "▶ 재생")

    def _on_player_error(self, code: int):
        song = self.current
        if song is None:
            return
        reason = "퍼가기 금지 영상" if code in EMBED_BLOCKED_ERRORS else f"오류 {code}"
        self.status(f"재생 불가({reason}) → 다음 곡: {song.display}")
        song.unplayable = True
        if it := self._item_of(song):
            self._refresh_item(it)
        self.play_next()

    # ---------------- 미리 검색 ----------------
    def prefetch_all(self):
        """아직 유튜브 ID가 없는 곡을 한 곡씩 차례로 검색 (동시에 100개 요청하지 않도록)."""
        if self._prefetching:
            return
        self._prefetching = True
        self._prefetch_next()

    def _prefetch_next(self):
        todo = [s for s in self.playlist().songs if not s.video_id and not s.unplayable]
        if not todo:
            self._prefetching = False
            self.status("미리 검색 완료")
            return
        song = todo[0]
        self.status(f"미리 검색 중 (남은 {len(todo)}곡): {song.display}", 0)

        def done(vid, s=song):
            self._on_searched(s, vid, play=False)
            self._prefetch_next()

        def fail(msg, s=song):
            s.unplayable = True
            self._prefetch_next()

        run_async(youtube.search_video_id, song.search_query, on_done=done, on_error=fail)

    # ---------------- 공통 ----------------
    def _show_error(self, msg: str):
        self.status("오류 발생")
        QMessageBox.critical(self, "오류", msg)
