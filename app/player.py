"""유튜브 IFrame Player를 Qt 창 안에 넣은 위젯.

동작 원리
1) 작은 로컬 HTTP 서버(127.0.0.1:임의포트)가 player.html을 제공한다.
   - 유튜브 임베드는 HTTP Referer(출처)가 없으면 'Error 153'으로 재생을 거부한다.
     file:// 이나 setHtml()로 띄우면 출처가 없어서 막히므로 진짜 http 주소로 띄운다.
2) QWebEngineView(내장 크롬)가 그 페이지를 열고, 페이지가 유튜브 IFrame API를 불러온다.
3) 파이썬 → JS : page.runJavaScript("loadVideo('ID')")
   JS → 파이썬 : console.log("YTEVENT:ended") 를 javaScriptConsoleMessage로 가로챔
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

# 유튜브 플레이어 상태 코드 (IFrame API 문서 기준)
STATE_UNSTARTED, STATE_ENDED, STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING, STATE_CUED = (
    -1, 0, 1, 2, 3, 5,
)
# 이 오류들은 '이 영상은 다른 사이트에 퍼가기 금지' 등 → 다음 곡으로 넘겨야 함
EMBED_BLOCKED_ERRORS = {101, 150, 153}

PLAYER_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="referrer" content="strict-origin-when-cross-origin">
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}#player{width:100%;height:100%}</style>
</head><body>
<div id="player"></div>
<script>
  var player = null, ready = false, pending = null;
  function emit(msg){ console.log("YTEVENT:" + msg); }

  function onYouTubeIframeAPIReady(){
    player = new YT.Player('player', {
      width: '100%', height: '100%',
      playerVars: { autoplay: 1, playsinline: 1, rel: 0, origin: location.origin },
      events: {
        onReady: function(){ ready = true; emit("ready"); if (pending){ loadVideo(pending); pending = null; } },
        onStateChange: function(e){ emit("state:" + e.data); },
        onError: function(e){ emit("error:" + e.data); }
      }
    });
  }
  function loadVideo(id){ if(!ready){ pending = id; return; } player.loadVideoById(id); }
  function togglePlay(){
    if(!ready) return;
    if (player.getPlayerState() === YT.PlayerState.PLAYING) player.pauseVideo(); else player.playVideo();
  }
  function setVolume(v){ if(ready) player.setVolume(v); }
  function stopVideo(){ if(ready) player.stopVideo(); }
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server 규칙)
        body = PLAYER_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 콘솔에 접속 로그 안 찍기
        pass


class _LocalServer:
    """player.html 하나만 제공하는 로컬 서버 (앱 종료 시 같이 꺼짐)."""

    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/player.html"

    def close(self):
        self.httpd.shutdown()


class _Page(QWebEnginePage):
    event = Signal(str)

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
        if message.startswith("YTEVENT:"):
            self.event.emit(message[len("YTEVENT:"):])


class YouTubePlayer(QWidget):
    ready = Signal()
    ended = Signal()
    state_changed = Signal(int)
    error = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = _LocalServer()

        self.view = QWebEngineView(self)
        page = _Page(self.view)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        page.event.connect(self._on_js_event)
        self.view.setPage(page)
        self.view.setUrl(QUrl(self._server.url))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    # ---- 파이썬 → JS ----
    def _js(self, code: str) -> None:
        self.view.page().runJavaScript(code)

    def play_video(self, video_id: str) -> None:
        safe = "".join(c for c in video_id if c.isalnum() or c in "-_")  # JS 주입 방지
        self._js(f"loadVideo('{safe}')")

    def toggle_play(self) -> None:
        self._js("togglePlay()")

    def stop(self) -> None:
        self._js("stopVideo()")

    def set_volume(self, volume: int) -> None:
        self._js(f"setVolume({int(volume)})")

    # ---- JS → 파이썬 ----
    def _on_js_event(self, msg: str) -> None:
        if msg == "ready":
            self.ready.emit()
        elif msg.startswith("state:"):
            state = int(msg.split(":", 1)[1])
            self.state_changed.emit(state)
            if state == STATE_ENDED:
                self.ended.emit()
        elif msg.startswith("error:"):
            self.error.emit(int(msg.split(":", 1)[1]))

    def shutdown(self) -> None:
        self._server.close()
