import pandas as pd

from bot.strategy.base import BaseStrategy, StrategyResult, Signal
from bot.analysis.indicators import add_rsi, add_macd, add_ema
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class MultiTimeframeMomentumStrategy(BaseStrategy):
    """멀티타임프레임 모멘텀 전략.

    4시간/1시간/15분 봉 모두 상승 정렬 시 매수.
    2개 이상 하락 전환 시 매도.
    """

    name = "momentum_mtf"

    def __init__(self, timeframes: list[str] = None, rsi_period: int = 14,
                 macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9):
        self.timeframes = timeframes or ["minute240", "minute60", "minute15"]
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def get_required_candle_count(self) -> int:
        return 50

    def get_preferred_interval(self) -> str:
        return self.timeframes[0]

    def _analyze_timeframe(self, df: pd.DataFrame) -> dict:
        """단일 타임프레임 분석 결과 반환."""
        if df is None or len(df) < 30:
            return {"bullish": False, "score": 0, "valid": False}

        rsi = add_rsi(df, self.rsi_period)
        macd_line, macd_signal, macd_hist = add_macd(
            df, self.macd_fast, self.macd_slow, self.macd_signal
        )
        ema20 = add_ema(df, 20)

        curr_rsi = rsi.iloc[-1]
        curr_macd_hist = macd_hist.iloc[-1]
        curr_price = df.iloc[-1]["close"]
        curr_ema20 = ema20.iloc[-1]

        if pd.isna(curr_rsi) or pd.isna(curr_macd_hist) or pd.isna(curr_ema20):
            return {"bullish": False, "score": 0, "valid": False}

        bullish_signals = 0
        total_signals = 3

        if curr_rsi > 50:
            bullish_signals += 1
        if curr_macd_hist > 0:
            bullish_signals += 1
        if curr_price > curr_ema20:
            bullish_signals += 1

        return {
            "bullish": bullish_signals >= 2,
            "score": bullish_signals / total_signals,
            "rsi": curr_rsi,
            "macd_hist": curr_macd_hist,
            "above_ema": curr_price > curr_ema20,
            "valid": True,
        }

    def analyze(self, ticker: str, df: pd.DataFrame, **kwargs) -> StrategyResult:
        """멀티타임프레임 분석.

        kwargs에 'ohlcv_by_timeframe' 딕셔너리가 필요합니다.
        없으면 단일 타임프레임으로 분석합니다.
        """
        ohlcv_map = kwargs.get("ohlcv_by_timeframe", {})

        if not ohlcv_map:
            # 단일 타임프레임 폴백
            result = self._analyze_timeframe(df)
            if not result["valid"]:
                return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "데이터 부족")

            if result["bullish"]:
                return StrategyResult(
                    Signal.BUY, result["score"] * 0.6, ticker,
                    "단일 타임프레임 상승 (멀티TF 데이터 부족)",
                    result,
                )
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "신호 없음", result)

        # 멀티타임프레임 분석
        tf_results = {}
        for tf in self.timeframes:
            tf_df = ohlcv_map.get(tf)
            if tf_df is not None:
                tf_results[tf] = self._analyze_timeframe(tf_df)
            else:
                tf_results[tf] = {"bullish": False, "score": 0, "valid": False}

        valid_count = sum(1 for r in tf_results.values() if r["valid"])
        if valid_count < 2:
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "유효 타임프레임 부족")

        bullish_count = sum(1 for r in tf_results.values() if r.get("bullish"))
        bearish_count = valid_count - bullish_count
        avg_score = sum(r["score"] for r in tf_results.values() if r["valid"]) / valid_count

        metadata = {
            "timeframe_results": {k: v for k, v in tf_results.items()},
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "avg_score": avg_score,
        }

        # 전체 상승 정렬
        if bullish_count == valid_count:
            confidence = min(avg_score + 0.2, 1.0)
            return StrategyResult(
                Signal.STRONG_BUY if confidence >= 0.8 else Signal.BUY,
                confidence, ticker,
                f"전 타임프레임 상승 정렬 ({bullish_count}/{valid_count})",
                metadata,
            )

        # 대부분 상승
        if bullish_count >= valid_count - 1 and bullish_count >= 2:
            return StrategyResult(
                Signal.BUY, avg_score * 0.7, ticker,
                f"상승 우세 ({bullish_count}/{valid_count})",
                metadata,
            )

        # 2개 이상 하락
        if bearish_count >= 2:
            return StrategyResult(
                Signal.SELL, 0.6, ticker,
                f"하락 전환 ({bearish_count}/{valid_count} 하락)",
                metadata,
            )

        return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "혼조세", metadata)
