"""오래 걸리는 작업(멜론 요청, 유튜브 검색)을 백그라운드 스레드에서 돌리는 도우미.

GUI 스레드에서 네트워크 요청을 하면 창이 멈추므로 반드시 이걸 거친다.

사용법:
    run_async(fetch_chart, on_done=self._chart_loaded, on_error=self._show_error)
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 - GUI에 메시지로 보여주기 위해 전부 잡음
            self._emit(self.signals.error, str(e))
        else:
            self._emit(self.signals.done, result)

    @staticmethod
    def _emit(signal, value) -> None:
        try:
            signal.emit(value)
        except RuntimeError:
            pass  # 작업 도중 창을 닫아 신호 대상이 이미 사라진 경우


_active: set[_Task] = set()  # 작업이 끝나기 전에 가비지 컬렉션되지 않도록 보관


def run_async(fn, *args, on_done=None, on_error=None, **kwargs) -> None:
    task = _Task(fn, *args, **kwargs)
    task.setAutoDelete(False)
    _active.add(task)

    def _cleanup(*_):
        _active.discard(task)

    if on_done:
        task.signals.done.connect(on_done)
    if on_error:
        task.signals.error.connect(on_error)
    task.signals.done.connect(_cleanup)
    task.signals.error.connect(_cleanup)
    QThreadPool.globalInstance().start(task)
