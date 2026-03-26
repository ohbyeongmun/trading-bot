import time
from typing import Optional

from bot.exchange.upbit_client import UpbitClient
from bot.risk.risk_manager import RiskManager
from bot.risk.position_sizer import PositionSizer
from bot.data.database import Database
from bot.utils.logger import get_logger

logger = get_logger(__name__)

UPBIT_FEE_RATE = 0.0005  # 0.05%


class OrderManager:
    """주문 관리: 리스크 확인 → 주문 실행 → DB 기록."""

    def __init__(self, client: UpbitClient, risk_manager: RiskManager,
                 position_sizer: PositionSizer, db: Database,
                 notifier=None, dry_run: bool = False):
        self.client = client
        self.risk_manager = risk_manager
        self.position_sizer = position_sizer
        self.db = db
        self.notifier = notifier
        self.dry_run = dry_run

    def execute_buy(self, ticker: str, amount_krw: float, strategy: str,
                    confidence: float = 0.0, reason: str = "") -> Optional[dict]:
        """매수 실행."""
        # 잔고 확인
        krw_balance = self.client.get_krw_balance()
        open_count = len(self.db.get_open_positions())

        # 리스크 승인
        approved, msg = self.risk_manager.approve_order(amount_krw, krw_balance, open_count)
        if not approved:
            logger.info(f"매수 거부: {ticker} | {msg}")
            return None

        # 이미 포지션 있는지 확인
        existing = self.db.get_open_position_by_ticker(ticker)
        if existing:
            logger.info(f"이미 포지션 보유: {ticker}")
            return None

        # 잔고 재확인 후 조정
        amount_krw = min(amount_krw, krw_balance * 0.995)  # 수수료 여유분
        if amount_krw < 5000:
            logger.info(f"매수 금액 부족: {amount_krw:.0f}원")
            return None

        if self.dry_run:
            logger.info(f"[DRY RUN] 매수: {ticker} | {amount_krw:,.0f}원 | {strategy}")
            price = self.client.get_current_price(ticker)
            if not price:
                return None
            volume = amount_krw / price
            self.db.open_position(ticker, price, volume, amount_krw, strategy)
            self.db.record_trade(ticker, "buy", amount_krw, volume, price,
                                 strategy, confidence, reason, amount_krw * UPBIT_FEE_RATE)
            return {"dry_run": True, "ticker": ticker, "amount": amount_krw}

        # 실제 매수
        result = self.client.buy_market(ticker, amount_krw)
        if not result or "error" in result:
            logger.error(f"매수 실패: {ticker} | {result}")
            return None

        # 체결 확인 (최대 5초 대기)
        order_uuid = result.get("uuid", "")
        price = self._wait_for_fill(order_uuid, ticker)
        if not price:
            price = self.client.get_current_price(ticker) or 0
        volume = self.client.get_balance(ticker)
        fee = amount_krw * UPBIT_FEE_RATE

        # DB 기록
        self.db.open_position(ticker, price, volume, amount_krw, strategy)
        self.db.record_trade(ticker, "buy", amount_krw, volume, price,
                             strategy, confidence, reason, fee, order_uuid)

        logger.info(f"매수 완료: {ticker} | {price:,.0f}원 | {volume:.8f}개 | {strategy}")
        print(f"  >>> 매수 완료: {ticker} | {price:,.0f}원 | {amount_krw:,.0f}원 | {strategy}", flush=True)

        # 알림
        if self.notifier:
            self.notifier.send_trade_sync(
                f"매수 | {ticker} | {amount_krw:,.0f}원 | {price:,.0f}원 | {strategy}"
            )

        return result

    def execute_sell(self, ticker: str, reason: str = "",
                     strategy: str = "") -> Optional[dict]:
        """매도 실행."""
        volume = self.client.get_balance(ticker)
        if volume <= 0:
            # DB에서 포지션 정리
            pos = self.db.get_open_position_by_ticker(ticker)
            if pos:
                self.db.close_position(pos.id, 0)
            return None

        current_price = self.client.get_current_price(ticker)
        if not current_price:
            return None

        position = self.db.get_open_position_by_ticker(ticker)

        if self.dry_run:
            amount_krw = volume * current_price
            logger.info(f"[DRY RUN] 매도: {ticker} | {amount_krw:,.0f}원 | {reason}")
            if position:
                self.db.close_position(position.id, current_price)
            self.db.record_trade(ticker, "sell", amount_krw, volume, current_price,
                                 strategy or (position.strategy if position else ""),
                                 0, reason, amount_krw * UPBIT_FEE_RATE)
            return {"dry_run": True, "ticker": ticker, "amount": amount_krw}

        # 실제 매도
        result = self.client.sell_market(ticker, volume)
        if not result or "error" in result:
            logger.error(f"매도 실패: {ticker} | {result}")
            return None

        order_uuid = result.get("uuid", "")
        sell_price = self._wait_for_fill(order_uuid, ticker) or current_price
        amount_krw = volume * sell_price
        fee = amount_krw * UPBIT_FEE_RATE

        # 포지션 닫기
        if position:
            self.db.close_position(position.id, sell_price)
            pnl = (sell_price - position.entry_price) * volume
            self.risk_manager.record_loss(pnl if pnl < 0 else 0)

        self.db.record_trade(ticker, "sell", amount_krw, volume, sell_price,
                             strategy or (position.strategy if position else ""),
                             0, reason, fee, order_uuid)

        logger.info(f"매도 완료: {ticker} | {sell_price:,.0f}원 | {reason}")
        pnl_display = ""
        if position:
            pnl_pct_val = (sell_price / position.entry_price - 1) * 100
            pnl_display = f" | PnL: {pnl_pct_val:+.2f}%"
        print(f"  <<< 매도 완료: {ticker} | {sell_price:,.0f}원 | {reason}{pnl_display}", flush=True)

        if self.notifier:
            pnl_str = ""
            if position:
                pnl_pct = (sell_price / position.entry_price - 1) * 100
                pnl_str = f" | PnL: {pnl_pct:+.2f}%"
            self.notifier.send_trade_sync(
                f"매도 | {ticker} | {amount_krw:,.0f}원 | {sell_price:,.0f}원 | {reason}{pnl_str}"
            )

        return result

    def sell_all_positions(self, reason: str = "전량 매도"):
        """모든 오픈 포지션 매도."""
        positions = self.db.get_open_positions()
        for pos in positions:
            self.execute_sell(pos.ticker, reason=reason, strategy=pos.strategy)
            time.sleep(0.5)

    def _wait_for_fill(self, order_uuid: str, ticker: str,
                       timeout: float = 5.0) -> Optional[float]:
        """주문 체결 대기 후 체결 가격 반환."""
        if not order_uuid:
            return None
        start = time.time()
        while time.time() - start < timeout:
            try:
                order = self.client.get_order(order_uuid)
                if order and order.get("state") == "done":
                    trades = order.get("trades", [])
                    if trades:
                        total_price = sum(float(t["price"]) * float(t["volume"]) for t in trades)
                        total_vol = sum(float(t["volume"]) for t in trades)
                        return total_price / total_vol if total_vol > 0 else None
                    return float(order.get("price", 0)) or None
            except Exception:
                pass
            time.sleep(0.5)
        return None
