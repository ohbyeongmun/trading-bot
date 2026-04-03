from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_balance: float
    daily_pnl: float
    daily_pnl_pct: float
    weekly_pnl_pct: float
    monthly_pnl_pct: float
    open_positions: int
    bot_status: str  # "running" | "stopped" | "paused"
    market_regime: str  # "bull" | "bear" | "sideways"


class PositionResponse(BaseModel):
    id: int
    ticker: str
    entry_price: float
    volume: float
    amount_krw: float
    strategy: str
    entry_time: Optional[datetime]
    highest_price: float
    current_price: Optional[float] = None
    pnl_pct: Optional[float] = None


class TradeResponse(BaseModel):
    id: int
    ticker: str
    side: str
    amount_krw: float
    volume: float
    price: float
    strategy: str
    confidence: float
    reason: str
    fee: float
    timestamp: Optional[datetime]


class StrategyStatsResponse(BaseModel):
    name: str
    total_trades: int
    win_rate: float
    avg_profit_pct: float
    avg_loss_pct: float
    total_pnl: float


class DailyReportResponse(BaseModel):
    date: date
    starting_balance: float
    ending_balance: float
    pnl: float
    pnl_pct: float
    trades_count: int
    win_rate: float
    max_drawdown: float


class BotStatusResponse(BaseModel):
    status: str
    message: str
