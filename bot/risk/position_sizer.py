import math

from bot.core.config import RiskConfig
from bot.utils.logger import get_logger

logger = get_logger(__name__)

UPBIT_MIN_ORDER_KRW = 5000


class PositionSizer:
    """포지션 크기 결정: 잔고를 최대 보유 수로 균등 분배."""

    def __init__(self, config: RiskConfig):
        self.config = config

    def calculate(self, capital: float, strategy_confidence: float,
                  win_rate: float = 0.5, avg_win: float = 0.03,
                  avg_loss: float = 0.03) -> float:
        """잔고 / 최대보유수 = 1종목당 금액. 단순하고 확실함."""
        max_coins = max(self.config.max_portfolio_coins, 1)
        amount = capital / max_coins

        # 1000원 단위 절사
        amount = math.floor(amount / 1000) * 1000

        # 최소 주문 금액
        if amount < UPBIT_MIN_ORDER_KRW:
            amount = 0

        logger.debug(f"포지션 사이즈: {amount:,.0f}원 (잔고 {capital:,.0f} / {max_coins}종목)")
        return amount
