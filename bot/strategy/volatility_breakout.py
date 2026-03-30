import pandas as pd
import numpy as np

from bot.strategy.base import BaseStrategy, StrategyResult, Signal
from bot.analysis.indicators import calculate_noise_ratio
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class VolatilityBreakoutStrategy(BaseStrategy):
    """래리 윌리엄스 변동성 돌파 전략 (한국 시장 최적화).

    진입: 현재가 > 시가 + (전일 고가 - 전일 저가) * k
    퇴장: 매일 09:00 KST 일괄 매도 (엔진에서 처리)
    """

    name = "volatility_breakout"

    def __init__(self, default_k: float = 0.5, use_dynamic_k: bool = True,
                 noise_filter: bool = True, lookback_days: int = 10):
        self.default_k = default_k
        self.use_dynamic_k = use_dynamic_k
        self.noise_filter = noise_filter
        self.lookback_days = lookback_days

    def get_required_candle_count(self) -> int:
        return max(self.lookback_days + 2, 20)

    def get_preferred_interval(self) -> str:
        return "day"

    def optimize_k(self, df: pd.DataFrame) -> float:
        """최근 N일 백테스트로 최적 k값 탐색 (0.1~0.9)."""
        if len(df) < self.lookback_days + 2:
            return self.default_k

        best_k = self.default_k
        best_return = -float("inf")

        for k_val in np.arange(0.1, 1.0, 0.1):
            total_return = 0.0
            trade_count = 0

            for i in range(2, min(len(df), self.lookback_days + 2)):
                prev = df.iloc[i - 1]
                curr = df.iloc[i]
                prev_range = prev["high"] - prev["low"]
                target_price = curr["open"] + prev_range * k_val

                if curr["high"] >= target_price and target_price > 0:
                    # 목표가에 매수, 종가에 매도 가정
                    buy_price = target_price
                    sell_price = curr["close"]
                    ret = (sell_price - buy_price) / buy_price
                    # 수수료 차감 (0.05% * 2)
                    ret -= 0.001
                    total_return += ret
                    trade_count += 1

            if trade_count > 0 and total_return > best_return:
                best_return = total_return
                best_k = round(k_val, 1)

        logger.debug(f"최적 k값: {best_k} (최근 수익률: {best_return:.4f})")
        return best_k

    def analyze(self, ticker: str, df: pd.DataFrame, **kwargs) -> StrategyResult:
        if len(df) < 3:
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "데이터 부족")

        current_price = kwargs.get("current_price")
        if current_price is None:
            current_price = df.iloc[-1]["close"]

        # 노이즈 필터: 전일 노이즈 비율이 높으면 스킵
        if self.noise_filter:
            noise = calculate_noise_ratio(df)
            if len(noise) >= 2 and noise.iloc[-2] > 0.55:
                return StrategyResult(
                    Signal.NEUTRAL, 0.0, ticker,
                    f"노이즈 비율 높음 ({noise.iloc[-2]:.2f} > 0.55)",
                    {"noise_ratio": noise.iloc[-2]},
                )

        # k값 결정
        k = self.optimize_k(df) if self.use_dynamic_k else self.default_k

        # 목표가 계산
        yesterday = df.iloc[-2]
        today = df.iloc[-1]
        prev_range = yesterday["high"] - yesterday["low"]
        target_price = today["open"] + prev_range * k

        if target_price <= 0:
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "목표가 계산 불가")

        # 돌파 여부 확인
        if current_price >= target_price:
            # 돌파 강도에 따라 신뢰도 계산
            breakout_pct = (current_price - target_price) / target_price
            confidence = min(0.4 + breakout_pct * 5, 1.0)

            return StrategyResult(
                Signal.STRONG_BUY if confidence >= 0.6 else Signal.BUY,
                confidence,
                ticker,
                f"변동성 돌파 (k={k:.1f}, 목표가={target_price:,.0f}, 현재가={current_price:,.0f})",
                {
                    "k": k,
                    "target_price": target_price,
                    "breakout_pct": breakout_pct,
                    "prev_range": prev_range,
                },
            )

        # 아직 돌파 전
        distance_pct = (target_price - current_price) / target_price
        return StrategyResult(
            Signal.NEUTRAL, 0.0, ticker,
            f"돌파 대기 (목표가={target_price:,.0f}, 거리={distance_pct:.2%})",
            {"k": k, "target_price": target_price, "distance_pct": distance_pct},
        )
