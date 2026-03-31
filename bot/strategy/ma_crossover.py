import pandas as pd

from bot.strategy.base import BaseStrategy, StrategyResult, Signal
from bot.analysis.indicators import add_ema, add_adx, add_volume_sma
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class MACrossoverStrategy(BaseStrategy):
    """이동평균 크로스오버 + 거래량 확인 + ADX 추세 필터.

    매수: EMA5 > EMA20 골든크로스 + 거래량 급증 + ADX > 25
    매도: EMA5 < EMA20 데드크로스
    """

    name = "ma_crossover"

    def __init__(self, fast_period: int = 5, slow_period: int = 20,
                 volume_multiplier: float = 2.0, adx_threshold: int = 25):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.volume_multiplier = volume_multiplier
        self.adx_threshold = adx_threshold

    def get_required_candle_count(self) -> int:
        return self.slow_period + 20

    def get_preferred_interval(self) -> str:
        return "minute60"

    def analyze(self, ticker: str, df: pd.DataFrame, **kwargs) -> StrategyResult:
        if len(df) < self.get_required_candle_count():
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "데이터 부족")

        fast_ema = add_ema(df, self.fast_period)
        slow_ema = add_ema(df, self.slow_period)
        adx = add_adx(df, 14)
        vol_sma = add_volume_sma(df, 20)

        curr_fast = fast_ema.iloc[-1]
        curr_slow = slow_ema.iloc[-1]
        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]
        curr_adx = adx.iloc[-1]
        curr_volume = df.iloc[-1]["volume"]
        curr_vol_sma = vol_sma.iloc[-1]

        if pd.isna(curr_fast) or pd.isna(curr_slow) or pd.isna(curr_adx):
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "지표 계산 불가")

        metadata = {
            "fast_ema": curr_fast,
            "slow_ema": curr_slow,
            "adx": curr_adx,
            "volume_ratio": curr_volume / curr_vol_sma if curr_vol_sma > 0 else 0,
        }

        # 골든크로스 감지
        golden_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        # 데드크로스 감지
        death_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        # ADX 추세 확인
        is_trending = curr_adx > self.adx_threshold
        # 거래량 급증 확인
        volume_confirmed = (curr_vol_sma > 0 and
                            curr_volume >= curr_vol_sma * self.volume_multiplier)

        # 매수: 골든크로스 (조건 완화 - ADX/거래량 옵션)
        if golden_cross:
            confidence = 0.5  # 골든크로스 자체만으로 0.5
            if is_trending:
                confidence += 0.2
            if volume_confirmed:
                confidence += 0.2
            confidence = min(confidence, 1.0)

            return StrategyResult(
                Signal.STRONG_BUY if confidence >= 0.7 else Signal.BUY,
                confidence, ticker,
                f"골든크로스 (ADX={curr_adx:.1f}, 거래량x{metadata['volume_ratio']:.1f})",
                metadata,
            )

        # 상승 추세 유지 중 (fast > slow) - 조건 완화
        if curr_fast > curr_slow:
            spread = (curr_fast - curr_slow) / curr_slow
            confidence = 0.3
            if is_trending:
                confidence = 0.4
            if volume_confirmed:
                confidence += 0.15
            if spread > 0.005:  # 0.5% 스프레드 (기존 1%)
                return StrategyResult(
                    Signal.BUY, confidence, ticker,
                    f"상승 추세 유지 (스프레드={spread:.4f})",
                    metadata,
                )

        # 매도: 데드크로스
        if death_cross:
            confidence = 0.6
            if is_trending:
                confidence = 0.8
            return StrategyResult(
                Signal.STRONG_SELL if confidence >= 0.8 else Signal.SELL,
                confidence, ticker,
                f"데드크로스 (ADX={curr_adx:.1f})",
                metadata,
            )

        # 하락 추세 유지
        if curr_fast < curr_slow:
            return StrategyResult(
                Signal.SELL, 0.3, ticker,
                "하락 추세 유지",
                metadata,
            )

        return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "신호 없음", metadata)
