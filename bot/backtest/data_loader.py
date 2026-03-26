import time
from typing import Optional

import pyupbit
import pandas as pd

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class DataLoader:
    """백테스트용 과거 데이터 로더."""

    @staticmethod
    def load_ohlcv(ticker: str, interval: str = "day", count: int = 200,
                   to: Optional[str] = None) -> Optional[pd.DataFrame]:
        try:
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count, to=to)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"데이터 로드 실패 {ticker}: {e}")
        return None

    @staticmethod
    def load_extended_ohlcv(ticker: str, interval: str = "day",
                            count: int = 1000) -> Optional[pd.DataFrame]:
        """200개 이상 캔들을 페이지네이션으로 로드."""
        frames = []
        remaining = count
        to = None

        while remaining > 0:
            fetch = min(remaining, 200)
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=fetch, to=to)
            if df is None or df.empty:
                break
            frames.append(df)
            remaining -= len(df)
            if len(df) < fetch:
                break
            to = str(df.index[0])
            time.sleep(0.2)

        if not frames:
            return None
        result = pd.concat(frames)
        result = result[~result.index.duplicated(keep="first")]
        return result.sort_index()

    @staticmethod
    def get_available_tickers() -> list[str]:
        tickers = pyupbit.get_tickers(fiat="KRW")
        return tickers if tickers else []
