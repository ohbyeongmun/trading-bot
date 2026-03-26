from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import func

from bot.data.models import Base, Trade, Position, DailyReport, create_db_engine, create_session
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, db_path: str = "data/trading_bot.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_db_engine(db_path)
        self._session = create_session(self._engine)

    def record_trade(self, ticker: str, side: str, amount_krw: float,
                     volume: float, price: float, strategy: str,
                     confidence: float = 0.0, reason: str = "",
                     fee: float = 0.0, order_uuid: str = "") -> Trade:
        trade = Trade(
            ticker=ticker, side=side, amount_krw=amount_krw,
            volume=volume, price=price, strategy=strategy,
            confidence=confidence, reason=reason, fee=fee,
            order_uuid=order_uuid, timestamp=datetime.utcnow(),
        )
        self._session.add(trade)
        self._session.commit()
        logger.info(f"거래 기록: {side} {ticker} | {amount_krw:,.0f}원 | {strategy}")
        return trade

    def open_position(self, ticker: str, entry_price: float, volume: float,
                      amount_krw: float, strategy: str) -> Position:
        position = Position(
            ticker=ticker, entry_price=entry_price, volume=volume,
            amount_krw=amount_krw, strategy=strategy,
            highest_price=entry_price, status="open",
            entry_time=datetime.utcnow(),
        )
        self._session.add(position)
        self._session.commit()
        return position

    def close_position(self, position_id: int, exit_price: float) -> Optional[Position]:
        pos = self._session.query(Position).filter_by(id=position_id).first()
        if not pos:
            return None
        pos.status = "closed"
        pos.exit_price = exit_price
        pos.exit_time = datetime.utcnow()
        pos.pnl = (exit_price - pos.entry_price) * pos.volume
        pos.pnl_pct = ((exit_price / pos.entry_price) - 1) * 100
        self._session.commit()
        return pos

    def update_highest_price(self, position_id: int, price: float):
        pos = self._session.query(Position).filter_by(id=position_id).first()
        if pos and price > pos.highest_price:
            pos.highest_price = price
            self._session.commit()

    def get_open_positions(self) -> list[Position]:
        return self._session.query(Position).filter_by(status="open").all()

    def get_open_position_by_ticker(self, ticker: str) -> Optional[Position]:
        return (self._session.query(Position)
                .filter_by(ticker=ticker, status="open")
                .first())

    def get_trades_today(self) -> list[Trade]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return self._session.query(Trade).filter(Trade.timestamp >= today).all()

    def get_trades_range(self, start: datetime, end: datetime) -> list[Trade]:
        return (self._session.query(Trade)
                .filter(Trade.timestamp >= start, Trade.timestamp <= end)
                .all())

    def get_daily_pnl(self) -> float:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        closed = (self._session.query(Position)
                  .filter(Position.exit_time >= today, Position.status == "closed")
                  .all())
        return sum(p.pnl or 0.0 for p in closed)

    def get_strategy_stats(self, strategy_name: str, days: int = 30) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        positions = (self._session.query(Position)
                     .filter(Position.strategy == strategy_name,
                             Position.status == "closed",
                             Position.exit_time >= since)
                     .all())
        if not positions:
            return {"win_rate": 0.5, "avg_win": 0.03, "avg_loss": 0.03, "total": 0}

        wins = [p for p in positions if (p.pnl or 0) > 0]
        losses = [p for p in positions if (p.pnl or 0) <= 0]

        win_rate = len(wins) / len(positions) if positions else 0.5
        avg_win = (sum(p.pnl_pct or 0 for p in wins) / len(wins) / 100) if wins else 0.03
        avg_loss = (abs(sum(p.pnl_pct or 0 for p in losses) / len(losses)) / 100) if losses else 0.03

        return {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total": len(positions),
        }

    def save_daily_report(self, report_date: date, starting_balance: float,
                          ending_balance: float, trades_count: int,
                          win_rate: float, max_drawdown: float,
                          best_trade: str = "", worst_trade: str = ""):
        pnl = ending_balance - starting_balance
        pnl_pct = (pnl / starting_balance * 100) if starting_balance > 0 else 0

        existing = self._session.query(DailyReport).filter_by(date=report_date).first()
        if existing:
            existing.starting_balance = starting_balance
            existing.ending_balance = ending_balance
            existing.pnl = pnl
            existing.pnl_pct = pnl_pct
            existing.trades_count = trades_count
            existing.win_rate = win_rate
            existing.max_drawdown = max_drawdown
            existing.best_trade = best_trade
            existing.worst_trade = worst_trade
        else:
            report = DailyReport(
                date=report_date, starting_balance=starting_balance,
                ending_balance=ending_balance, pnl=pnl, pnl_pct=pnl_pct,
                trades_count=trades_count, win_rate=win_rate,
                max_drawdown=max_drawdown, best_trade=best_trade,
                worst_trade=worst_trade,
            )
            self._session.add(report)
        self._session.commit()

    def get_peak_balance(self) -> float:
        result = self._session.query(func.max(DailyReport.ending_balance)).scalar()
        return result or 0.0
