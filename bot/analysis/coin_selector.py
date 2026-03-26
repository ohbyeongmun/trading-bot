import time

from bot.exchange.upbit_client import UpbitClient
from bot.core.config import CoinSelectionConfig
from bot.analysis.indicators import calculate_volatility
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class CoinSelector:
    """자동 코인 선정: 거래량/변동성 기반 상위 종목 선택."""

    def __init__(self, client: UpbitClient, config: CoinSelectionConfig):
        self.client = client
        self.config = config

    def get_tradeable_coins(self) -> list[str]:
        """거래 가능한 코인 목록을 점수순으로 반환."""
        all_tickers = self.client.get_all_krw_tickers()
        if not all_tickers:
            logger.error("KRW 마켓 티커를 가져올 수 없습니다")
            return []

        # 제외 코인 필터
        tickers = [t for t in all_tickers if t not in self.config.excluded_coins]

        scored = []
        for ticker in tickers:
            try:
                score = self._score_coin(ticker)
                if score is not None:
                    scored.append((ticker, score))
                time.sleep(0.15)  # 레이트 리밋
            except Exception as e:
                logger.debug(f"{ticker} 스코어링 실패: {e}")
                continue

        # 점수순 정렬
        scored.sort(key=lambda x: x[1], reverse=True)

        top_coins = [t for t, _ in scored[:self.config.max_coins_to_screen]]
        logger.info(f"코인 선정 완료: {len(top_coins)}개 / {len(tickers)}개 중")
        for t, s in scored[:self.config.max_coins_to_screen]:
            logger.debug(f"  {t}: score={s:.4f}")

        return top_coins

    def _score_coin(self, ticker: str) -> float | None:
        """코인 점수 계산: 변동성 * 0.6 + 거래량 * 0.4."""
        df = self.client.get_ohlcv(ticker, interval="day", count=8)
        if df is None or len(df) < 3:
            return None

        # 일 거래대금 확인 (최근 3일 평균)
        recent_volumes = df.tail(3)
        avg_volume_krw = (recent_volumes["close"] * recent_volumes["volume"]).mean()

        if avg_volume_krw < self.config.min_volume_krw:
            return None

        # 변동성 계산
        volatility = calculate_volatility(df, period=7)

        # 정규화된 점수 (볼륨은 로그 스케일)
        import math
        vol_score = min(volatility * 10, 1.0)  # 10% 변동성이면 만점
        volume_score = min(math.log10(avg_volume_krw / self.config.min_volume_krw + 1), 1.0)

        return vol_score * 0.6 + volume_score * 0.4

    def filter_by_current_volume(self, tickers: list[str], min_ratio: float = 0.5) -> list[str]:
        """실시간 거래량이 일평균 대비 일정 비율 이상인 코인만 필터."""
        filtered = []
        for ticker in tickers:
            try:
                df = self.client.get_ohlcv(ticker, interval="day", count=5)
                if df is None or len(df) < 2:
                    continue
                avg_vol = df["volume"].iloc[:-1].mean()
                today_vol = df["volume"].iloc[-1]
                if avg_vol > 0 and today_vol / avg_vol >= min_ratio:
                    filtered.append(ticker)
                time.sleep(0.1)
            except Exception:
                continue
        return filtered
