import time
import threading
from typing import Optional

import pyupbit
import pandas as pd

from bot.utils.logger import get_logger

logger = get_logger(__name__)



# 타임프레임별 캐시 TTL (초)
OHLCV_CACHE_TTL = {
    "minute1": 60,
    "minute3": 180,
    "minute5": 300,
    "minute15": 900,
    "minute30": 1800,
    "minute60": 3600,
    "minute240": 14400,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
}


class UpbitClient:
    """pyupbit 래퍼: 재시도 로직, 레이트 리밋, OHLCV 캐시, 로깅 포함."""

    # Upbit API 제한: 주문 10req/sec, 시세 30req/sec
    # 멀티 타임프레임 대응을 위해 간격 확대
    MIN_REQUEST_INTERVAL = 0.125  # 125ms (초당 8요청)

    def __init__(self, access_key: str, secret_key: str):
        self._upbit = pyupbit.Upbit(access_key, secret_key)
        self._lock = threading.Lock()
        self._last_request_time = 0.0
        self._ohlcv_cache: dict[tuple[str, str, int], dict] = {}

    def _rate_limit(self):
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
            self._last_request_time = time.time()

    def _retry(self, func, *args, max_retries: int = 3, **kwargs):
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                result = func(*args, **kwargs)
                if result is None and attempt < max_retries - 1:
                    logger.warning(f"API 반환값 None, 재시도 {attempt + 1}/{max_retries}")
                    time.sleep(1 * (attempt + 1))
                    continue
                return result
            except Exception as e:
                logger.error(f"API 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    raise

    def get_krw_balance(self) -> float:
        balance = self._retry(self._upbit.get_balance, "KRW")
        return float(balance) if balance else 0.0

    def get_balance(self, ticker: str) -> float:
        coin = ticker.replace("KRW-", "")
        balance = self._retry(self._upbit.get_balance, coin)
        return float(balance) if balance else 0.0

    def get_avg_buy_price(self, ticker: str) -> float:
        coin = ticker.replace("KRW-", "")
        price = self._retry(self._upbit.get_avg_buy_price, coin)
        return float(price) if price else 0.0

    def get_current_price(self, ticker: str) -> Optional[float]:
        try:
            price = self._retry(pyupbit.get_current_price, ticker)
            if price is not None:
                return float(price)

            # pyupbit 이상 반환(None)일 때, ohlcv에서 마지막 종가로 대체
            df = self.get_ohlcv(ticker, interval="minute1", count=1)
            if df is not None and not df.empty:
                close_price = df["close"].iloc[-1]
                logger.info(f"현재가 None 대체: {ticker} -> {close_price}")
                return float(close_price)

            logger.warning(f"현재가 수집 실패: {ticker} (None/ohlcv 없음)")
            return None
        except Exception as e:
            logger.warning(f"current_price 실패 ({ticker}): {e}")
            return None

    def get_current_prices(self, tickers: list[str]) -> dict[str, float]:
        prices = {}
        if not tickers:
            return prices

        # pyupbit.get_current_price에 리스트 전체를 넘기면 하나의 잘못된 코드 때문에 전체 실패함.
        # 따라서 개별 호출로 분리하고, 실패하는 티커는 건너뜀.
        for ticker in tickers:
            try:
                current_price = self.get_current_price(ticker)
                if current_price is not None:
                    prices[ticker] = current_price
                else:
                    logger.warning(f"가격 없음: {ticker}, 생략")
            except Exception as e:
                logger.warning(f"유효하지 않은 티커 또는 API 오류: {ticker}, 건너뜁니다 ({e})")
        return prices

    def get_ohlcv(
        self,
        ticker: str,
        interval: str = "day",
        count: int = 200,
        to: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        # 캐시 확인 (to 파라미터가 없을 때만 캐시 사용)
        if to is None:
            cache_key = (ticker, interval, count)
            cached = self._ohlcv_cache.get(cache_key)
            if cached and time.time() < cached["expires_at"]:
                return cached["data"]

        df = self._retry(pyupbit.get_ohlcv, ticker, interval=interval, count=count, to=to)
        if df is not None and not df.empty:
            # 캐시 저장
            if to is None:
                ttl = OHLCV_CACHE_TTL.get(interval, 60)
                self._ohlcv_cache[(ticker, interval, count)] = {
                    "data": df,
                    "expires_at": time.time() + ttl,
                }
            return df
        return None

    def clear_ohlcv_cache(self):
        """캐시 수동 초기화."""
        self._ohlcv_cache.clear()

    def get_ohlcv_extended(
        self,
        ticker: str,
        interval: str = "day",
        count: int = 400,
    ) -> Optional[pd.DataFrame]:
        """200개 이상의 캔들 데이터를 페이지네이션으로 가져오기."""
        frames = []
        remaining = count
        to = None

        while remaining > 0:
            fetch_count = min(remaining, 200)
            df = self.get_ohlcv(ticker, interval=interval, count=fetch_count, to=to)
            if df is None or df.empty:
                break
            frames.append(df)
            remaining -= len(df)
            if len(df) < fetch_count:
                break
            to = str(df.index[0])
            time.sleep(0.2)

        if not frames:
            return None
        result = pd.concat(frames)
        result = result[~result.index.duplicated(keep="first")]
        return result.sort_index()

    def get_orderbook(self, ticker: str) -> Optional[dict]:
        return self._retry(pyupbit.get_orderbook, ticker)

    def get_all_krw_tickers(self) -> list[str]:
        tickers = self._retry(pyupbit.get_tickers, fiat="KRW")
        return tickers if tickers else []

    def buy_market(self, ticker: str, amount_krw: float) -> Optional[dict]:
        if amount_krw < 5000:
            logger.warning(f"최소 주문 금액 미달: {amount_krw:.0f}원 (최소 5,000원)")
            return None
        logger.info(f"시장가 매수: {ticker} | {amount_krw:,.0f}원")
        result = self._retry(self._upbit.buy_market_order, ticker, amount_krw)
        if result and "error" not in result:
            logger.info(f"매수 성공: {result.get('uuid', 'N/A')}")
        else:
            logger.error(f"매수 실패: {result}")
        return result

    def sell_market(self, ticker: str, volume: float) -> Optional[dict]:
        logger.info(f"시장가 매도: {ticker} | 수량: {volume}")
        result = self._retry(self._upbit.sell_market_order, ticker, volume)
        if result and "error" not in result:
            logger.info(f"매도 성공: {result.get('uuid', 'N/A')}")
        else:
            logger.error(f"매도 실패: {result}")
        return result

    def get_order(self, uuid: str) -> Optional[dict]:
        return self._retry(self._upbit.get_order, uuid)

    def get_balances(self) -> list[dict]:
        result = self._retry(self._upbit.get_balances)
        return result if result else []
