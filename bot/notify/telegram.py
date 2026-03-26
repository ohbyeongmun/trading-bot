import asyncio
import threading
from typing import Optional

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramNotifier:
    """텔레그램 알림 발송."""

    def __init__(self, token: str, chat_id: str, enabled: bool = True):
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self._bot = None

        if enabled and token and chat_id:
            try:
                from telegram import Bot
                self._bot = Bot(token=token)
                logger.info("텔레그램 알림 초기화 완료")
            except ImportError:
                logger.warning("python-telegram-bot 미설치. pip install python-telegram-bot")
            except Exception as e:
                logger.error(f"텔레그램 초기화 실패: {e}")

    async def send_message(self, text: str):
        if not self._bot or not self.enabled:
            logger.debug(f"[텔레그램 비활성] {text}")
            return
        try:
            await self._bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"텔레그램 발송 실패: {e}")

    def send_trade_sync(self, message: str):
        """동기 방식으로 거래 알림 전송."""
        text = f"<b>[거래]</b>\n{message}"
        self._send_sync(text)

    def send_alert_sync(self, message: str):
        text = f"<b>[알림]</b>\n{message}"
        self._send_sync(text)

    def send_daily_report_sync(self, date_str: str, starting: float, ending: float,
                                pnl: float, pnl_pct: float, trades_count: int,
                                win_rate: float, max_dd: float):
        sign = "+" if pnl >= 0 else ""
        text = (
            f"<b>[일일 리포트] {date_str}</b>\n"
            f"시작 잔고: {starting:,.0f}원\n"
            f"종료 잔고: {ending:,.0f}원\n"
            f"수익: {sign}{pnl:,.0f}원 ({sign}{pnl_pct:.2f}%)\n"
            f"거래 횟수: {trades_count}\n"
            f"승률: {win_rate:.1f}%\n"
            f"최대 낙폭: {max_dd:.2f}%"
        )
        self._send_sync(text)

    def send_error_sync(self, message: str):
        text = f"<b>[오류]</b>\n{message}"
        self._send_sync(text)

    def send_startup_sync(self, capital: float, coin_count: int, strategies: list[str]):
        text = (
            f"<b>[봇 시작]</b>\n"
            f"투자금: {capital:,.0f}원\n"
            f"선정 코인: {coin_count}개\n"
            f"전략: {', '.join(strategies)}"
        )
        self._send_sync(text)

    def _send_sync(self, text: str):
        if not self._bot or not self.enabled:
            logger.debug(f"[텔레그램 비활성] {text[:50]}...")
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.send_message(text))
            else:
                loop.run_until_complete(self.send_message(text))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.send_message(text))
            loop.close()
