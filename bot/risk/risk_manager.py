from datetime import datetime

from bot.core.config import RiskConfig
from bot.data.database import Database
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class RiskManager:
    """리스크 관리: 손절, 익절, 트레일링 스탑, 일일 손실 한도, 최대 낙폭."""

    def __init__(self, config: RiskConfig, db: Database, initial_capital: float):
        self.config = config
        self.db = db
        self.initial_capital = initial_capital
        self.peak_balance = max(initial_capital, db.get_peak_balance() or initial_capital)
        self._daily_loss = 0.0
        self._trading_paused = False
        self._pause_time = None

    @property
    def is_trading_paused(self) -> bool:
        return self._trading_paused

    def reset_daily(self):
        """일일 리셋 (09:00 KST)."""
        self._daily_loss = 0.0
        self._trading_paused = False
        logger.info("리스크 매니저 일일 리셋 완료")

    def update_peak_balance(self, current_balance: float):
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

    def record_loss(self, loss_amount: float):
        """손실 기록 (음수값 전달)."""
        if loss_amount < 0:
            self._daily_loss += abs(loss_amount)

    def can_trade(self, current_balance: float) -> tuple[bool, str]:
        """거래 가능 여부 확인."""
        if self._trading_paused:
            # 10분 후 자동 재개
            if self._pause_time:
                elapsed = (datetime.utcnow() - self._pause_time).total_seconds()
                if elapsed >= 600:
                    self._trading_paused = False
                    self._pause_time = None
                    logger.info("거래 일시 중지 자동 해제 (10분 경과)")
                else:
                    return False, f"거래 일시 중지됨 ({600 - elapsed:.0f}초 후 재개)"
            else:
                return False, "거래 일시 중지됨"

        # 일일 손실 한도 확인
        daily_loss_pct = self._daily_loss / self.initial_capital
        if daily_loss_pct >= self.config.daily_loss_limit_pct:
            self._trading_paused = True
            self._pause_time = datetime.utcnow()
            msg = f"일일 손실 한도 도달 ({daily_loss_pct:.2%} >= {self.config.daily_loss_limit_pct:.2%})"
            logger.warning(msg)
            return False, msg

        # 최대 낙폭 확인
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance
            if drawdown >= self.config.max_drawdown_pct:
                self._trading_paused = True
                self._pause_time = datetime.utcnow()
                msg = f"최대 낙폭 도달 ({drawdown:.2%} >= {self.config.max_drawdown_pct:.2%})"
                logger.warning(msg)
                return False, msg

        return True, "거래 가능"

    def check_stop_loss(self, entry_price: float, current_price: float) -> bool:
        """손절 확인. True면 매도 필요."""
        if entry_price <= 0:
            return False
        loss_pct = (current_price - entry_price) / entry_price
        return loss_pct <= -self.config.stop_loss_pct

    def check_take_profit(self, entry_price: float, current_price: float) -> bool:
        """익절 확인. True면 매도 필요."""
        if entry_price <= 0:
            return False
        profit_pct = (current_price - entry_price) / entry_price
        return profit_pct >= self.config.take_profit_pct

    def check_trailing_stop(self, highest_price: float, current_price: float) -> bool:
        """트레일링 스탑 확인. True면 매도 필요."""
        if highest_price <= 0:
            return False
        drop_pct = (highest_price - current_price) / highest_price
        return drop_pct >= self.config.trailing_stop_pct

    def approve_order(self, amount_krw: float, current_balance: float,
                      open_positions_count: int) -> tuple[bool, str]:
        """주문 승인 여부 확인."""
        # 거래 가능 상태 확인
        can, reason = self.can_trade(current_balance)
        if not can:
            return False, reason

        # 포트폴리오 코인 수 제한
        if open_positions_count >= self.config.max_portfolio_coins:
            return False, f"최대 코인 수 초과 ({open_positions_count}/{self.config.max_portfolio_coins})"

        # 포지션 크기 제한
        max_amount = current_balance * self.config.max_position_pct
        if amount_krw > max_amount:
            return False, f"포지션 크기 초과 ({amount_krw:,.0f} > {max_amount:,.0f})"

        # 잔고 확인
        if amount_krw > current_balance:
            return False, f"잔고 부족 ({amount_krw:,.0f} > {current_balance:,.0f})"

        return True, "승인"

    def get_exit_reason(self, entry_price: float, highest_price: float,
                        current_price: float, entry_time=None,
                        strategy: str = "") -> str | None:
        """퇴장 사유 반환. None이면 홀드."""
        if self.check_stop_loss(entry_price, current_price):
            loss_pct = (current_price - entry_price) / entry_price * 100
            return f"손절 ({loss_pct:.1f}%)"

        if self.check_take_profit(entry_price, current_price):
            profit_pct = (current_price - entry_price) / entry_price * 100
            return f"익절 ({profit_pct:.1f}%)"

        if self.check_trailing_stop(highest_price, current_price):
            drop_pct = (highest_price - current_price) / highest_price * 100
            return f"트레일링 스탑 (고점 대비 -{drop_pct:.1f}%)"

        # 시간 초과 강제 청산 (별도 청산 로직이 있는 전략 제외)
        fast_strategies = ("volatility_breakout", "fast_breakout", "momentum_surge", "volume_spike")
        if (entry_time and strategy not in fast_strategies):
            now = datetime.utcnow()
            et = entry_time
            if et.tzinfo is not None:
                et = et.replace(tzinfo=None)
            elapsed_min = (now - et).total_seconds() / 60
            if elapsed_min >= self.config.max_hold_minutes:
                change_pct = (current_price - entry_price) / entry_price * 100
                return f"시간 초과 청산 ({elapsed_min:.0f}분, {change_pct:+.1f}%)"

        return None
