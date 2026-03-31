import pandas as pd

from bot.strategy.base import BaseStrategy, StrategyResult, Signal
from bot.analysis.indicators import add_rsi, add_bollinger_bands, add_volume_sma
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class RSIBollingerStrategy(BaseStrategy):
    """RSI + 볼린저 밴드 평균회귀 전략.

    매수: RSI 과매도 + 볼린저 하단 터치 + 거래량 확인
    매도: RSI 과매수 OR 볼린저 상단 터치
    """

    name = "rsi_bollinger"

    def __init__(self, rsi_period: int = 14, rsi_oversold: int = 30,
                 rsi_overbought: int = 70, bb_period: int = 20,
                 bb_std: float = 2.0, volume_multiplier: float = 1.5):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_multiplier = volume_multiplier

    def get_required_candle_count(self) -> int:
        return max(self.rsi_period, self.bb_period) + 10

    def get_preferred_interval(self) -> str:
        return "minute60"

    def analyze(self, ticker: str, df: pd.DataFrame, **kwargs) -> StrategyResult:
        if len(df) < self.get_required_candle_count():
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "데이터 부족")

        # 지표 계산
        rsi = add_rsi(df, self.rsi_period)
        bb_upper, bb_mid, bb_lower = add_bollinger_bands(df, self.bb_period, self.bb_std)
        vol_sma = add_volume_sma(df, 20)

        current_rsi = rsi.iloc[-1]
        current_price = df.iloc[-1]["close"]
        current_volume = df.iloc[-1]["volume"]
        current_bb_upper = bb_upper.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_vol_sma = vol_sma.iloc[-1]

        if pd.isna(current_rsi) or pd.isna(current_bb_lower):
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "지표 계산 불가")

        metadata = {
            "rsi": current_rsi,
            "bb_upper": current_bb_upper,
            "bb_lower": current_bb_lower,
            "volume_ratio": current_volume / current_vol_sma if current_vol_sma > 0 else 0,
        }

        # 매수 신호: RSI 과매도 또는 볼린저 하단 근접 (완화)
        is_oversold = current_rsi < 45  # 45 이하면 매수 기회 (기존 30)
        near_lower_band = current_price <= current_bb_lower * 1.02  # 2% 여유 (기존 1%)
        volume_surge = (current_vol_sma > 0 and
                        current_volume >= current_vol_sma * 1.2)  # 1.2배 (기존 1.5배)

        if is_oversold and near_lower_band:
            confidence = 0.6
            if volume_surge:
                confidence = 0.8
            if current_rsi < 30:
                confidence = min(confidence + 0.15, 1.0)

            return StrategyResult(
                Signal.STRONG_BUY if confidence >= 0.8 else Signal.BUY,
                confidence, ticker,
                f"RSI({current_rsi:.1f}) + 볼린저 하단 근접",
                metadata,
            )

        # RSI만 낮거나 볼린저 하단 근접 (약한 매수)
        if is_oversold or near_lower_band:
            confidence = 0.35
            if volume_surge:
                confidence = 0.5
            return StrategyResult(
                Signal.BUY, confidence, ticker,
                f"RSI({current_rsi:.1f}) / BB하단({current_bb_lower:,.0f})",
                metadata,
            )

        # 매도 신호: RSI 과매수 OR 볼린저 상단 터치
        is_overbought = current_rsi > self.rsi_overbought
        near_upper_band = current_price >= current_bb_upper * 0.99

        if is_overbought or near_upper_band:
            confidence = 0.5
            if is_overbought and near_upper_band:
                confidence = 0.8
            if current_rsi > 80:
                confidence = min(confidence + 0.15, 1.0)

            return StrategyResult(
                Signal.STRONG_SELL if confidence >= 0.8 else Signal.SELL,
                confidence, ticker,
                f"RSI 과매수({current_rsi:.1f}) / 볼린저 상단 근접",
                metadata,
            )

        return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "신호 없음", metadata)
