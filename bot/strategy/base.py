from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum

import pandas as pd


class Signal(IntEnum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class StrategyResult:
    signal: Signal
    confidence: float  # 0.0 ~ 1.0
    ticker: str
    reason: str
    metadata: dict = field(default_factory=dict)


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def analyze(self, ticker: str, df: pd.DataFrame, **kwargs) -> StrategyResult:
        """OHLCV 데이터 분석 후 매매 신호 반환."""

    @abstractmethod
    def get_required_candle_count(self) -> int:
        """전략에 필요한 최소 캔들 수."""

    @abstractmethod
    def get_preferred_interval(self) -> str:
        """선호하는 캔들 간격: 'day', 'minute60', 'minute15' 등."""
