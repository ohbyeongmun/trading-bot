import time
from datetime import datetime
from typing import Callable

from bot.utils.helpers import now_kst
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TimeEvent:
    def __init__(self, hour: int, minute: int, callback: Callable, name: str = ""):
        self.hour = hour
        self.minute = minute
        self.callback = callback
        self.name = name or callback.__name__
        self._last_triggered_date = None

    def should_trigger(self, now: datetime) -> bool:
        today = now.date()
        if self._last_triggered_date == today:
            return False
        if now.hour == self.hour and now.minute == self.minute:
            return True
        return False

    def trigger(self):
        self._last_triggered_date = now_kst().date()
        logger.info(f"스케줄 이벤트 실행: {self.name}")
        try:
            self.callback()
        except Exception as e:
            logger.error(f"스케줄 이벤트 오류 [{self.name}]: {e}")


class Scheduler:
    """시간 기반 이벤트 스케줄러."""

    def __init__(self):
        self.events: list[TimeEvent] = []
        self._interval_callbacks: list[tuple[Callable, str]] = []

    def add_daily_event(self, hour: int, minute: int, callback: Callable, name: str = ""):
        event = TimeEvent(hour, minute, callback, name)
        self.events.append(event)
        logger.info(f"일일 이벤트 등록: {name} @ {hour:02d}:{minute:02d} KST")

    def add_interval_callback(self, callback: Callable, name: str = ""):
        self._interval_callbacks.append((callback, name or callback.__name__))

    def check_events(self):
        now = now_kst()
        for event in self.events:
            if event.should_trigger(now):
                event.trigger()

    def run_interval_callbacks(self):
        for callback, name in self._interval_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"인터벌 콜백 오류 [{name}]: {e}")

    def run_loop(self, interval_seconds: int = 10, stop_event=None):
        """메인 루프: 이벤트 체크 + 인터벌 콜백 반복 실행."""
        logger.info(f"스케줄러 시작 (간격: {interval_seconds}초)")
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                self.check_events()
                self.run_interval_callbacks()
            except KeyboardInterrupt:
                logger.info("스케줄러 중지 (KeyboardInterrupt)")
                break
            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}")
            time.sleep(interval_seconds)
