import math

from bot.core.config import RiskConfig
from bot.utils.logger import get_logger

logger = get_logger(__name__)

UPBIT_MIN_ORDER_KRW = 5000


class PositionSizer:
    """포지션 크기 결정: Kelly 공식 또는 고정 비율."""

    def __init__(self, config: RiskConfig):
        self.config = config

    def kelly_size(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Half-Kelly 공식으로 최적 투자 비율 계산.

        f* = (bp - q) / b
        b = avg_win / avg_loss, p = win_rate, q = 1 - p
        """
        if avg_loss <= 0 or win_rate <= 0:
            return self.config.max_position_pct * 0.5

        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b

        # Half-Kelly로 보수적 적용
        kelly *= self.config.kelly_fraction

        # 범위 제한: 0 ~ max_position_pct
        kelly = max(0.0, min(kelly, self.config.max_position_pct))

        # win_rate=0.5, avg_win==avg_loss이면 kelly=0이 되므로
        # 초기 전략에서 무리 없이 최소 매수하도록 낮은 고정값을 지원
        if kelly <= 0.0:
            kelly = max(self.config.max_position_pct * 0.3, 0.1)

        logger.debug(f"Kelly 계산: win_rate={p:.2f}, b={b:.2f}, f*={kelly:.4f}")
        return kelly

    def fixed_fractional_size(self) -> float:
        return self.config.max_position_pct

    def calculate(self, capital: float, strategy_confidence: float,
                  win_rate: float = 0.5, avg_win: float = 0.03,
                  avg_loss: float = 0.03) -> float:
        """최종 투자 금액(KRW) 계산.

        Args:
            capital: 현재 가용 자본금
            strategy_confidence: 전략 신뢰도 (0.0 ~ 1.0)
            win_rate, avg_win, avg_loss: Kelly 공식에 사용할 통계

        Returns:
            투자할 KRW 금액
        """
        if self.config.use_kelly:
            fraction = self.kelly_size(win_rate, avg_win, avg_loss)
        else:
            fraction = self.fixed_fractional_size()

        # 신뢰도에 따라 스케일링
        fraction *= max(strategy_confidence, 0.5)

        amount = capital * fraction

        # 최소/최대 제한
        max_amount = capital * self.config.max_position_pct
        amount = min(amount, max_amount)
        amount = max(amount, 0)

        # Upbit 최소 주문 금액
        if 0 < amount < UPBIT_MIN_ORDER_KRW:
            amount = UPBIT_MIN_ORDER_KRW

        # 1000원 단위 절사
        amount = math.floor(amount / 1000) * 1000

        # 재확인: 최소 주문 금액 아래면 없앰
        if amount < UPBIT_MIN_ORDER_KRW:
            amount = 0

        logger.debug(f"포지션 사이즈: {amount:,.0f}원 (자본금의 {amount / capital * 100:.1f}%)")
        return amount
