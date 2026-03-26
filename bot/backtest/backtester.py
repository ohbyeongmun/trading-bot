from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from bot.strategy.base import BaseStrategy, Signal
from bot.utils.logger import get_logger

logger = get_logger(__name__)

UPBIT_FEE = 0.0005  # 0.05%
SLIPPAGE = 0.0005   # 0.05%


@dataclass
class BacktestResult:
    ticker: str
    strategy_name: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"=== 백테스트 결과: {self.ticker} ({self.strategy_name}) ===\n"
            f"초기 자본: {self.initial_capital:,.0f}원\n"
            f"최종 자본: {self.final_capital:,.0f}원\n"
            f"총 수익률: {self.total_return_pct:+.2f}%\n"
            f"최대 낙폭: {self.max_drawdown_pct:.2f}%\n"
            f"샤프 비율: {self.sharpe_ratio:.2f}\n"
            f"승률: {self.win_rate:.1f}%\n"
            f"수익 팩터: {self.profit_factor:.2f}\n"
            f"총 거래: {self.total_trades}건\n"
        )


class Backtester:
    """전략 백테스트 엔진."""

    def __init__(self, strategy: BaseStrategy, initial_capital: float = 2_000_000,
                 fee_rate: float = UPBIT_FEE, slippage: float = SLIPPAGE):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage

    def run(self, ticker: str, df: pd.DataFrame,
            position_pct: float = 0.25) -> BacktestResult:
        """백테스트 실행."""
        if df is None or len(df) < self.strategy.get_required_candle_count() + 5:
            return self._empty_result(ticker)

        capital = self.initial_capital
        position = 0.0  # 보유 수량
        entry_price = 0.0
        equity_curve = []
        trades = []
        peak = capital

        min_candles = self.strategy.get_required_candle_count()

        for i in range(min_candles, len(df)):
            window = df.iloc[:i + 1]
            current_price = df.iloc[i]["close"]
            current_date = df.index[i]

            # 포트폴리오 가치
            portfolio_value = capital + position * current_price
            equity_curve.append({"date": current_date, "value": portfolio_value})
            peak = max(peak, portfolio_value)

            # 전략 분석
            result = self.strategy.analyze(ticker, window, current_price=current_price)

            # 매수
            if result.signal in (Signal.BUY, Signal.STRONG_BUY) and position == 0:
                invest_amount = capital * position_pct
                buy_price = current_price * (1 + self.slippage)
                fee = invest_amount * self.fee_rate
                volume = (invest_amount - fee) / buy_price

                position = volume
                entry_price = buy_price
                capital -= invest_amount
                trades.append({
                    "date": current_date, "side": "buy",
                    "price": buy_price, "amount": invest_amount,
                    "reason": result.reason,
                })

            # 매도
            elif result.signal in (Signal.SELL, Signal.STRONG_SELL) and position > 0:
                sell_price = current_price * (1 - self.slippage)
                proceeds = position * sell_price
                fee = proceeds * self.fee_rate
                pnl_pct = (sell_price / entry_price - 1) * 100

                capital += proceeds - fee
                trades.append({
                    "date": current_date, "side": "sell",
                    "price": sell_price, "amount": proceeds,
                    "pnl_pct": pnl_pct, "reason": result.reason,
                })
                position = 0
                entry_price = 0

            # 손절/익절 시뮬레이션
            elif position > 0:
                loss_pct = (current_price - entry_price) / entry_price
                if loss_pct <= -0.03:  # 3% 손절
                    sell_price = current_price * (1 - self.slippage)
                    proceeds = position * sell_price
                    fee = proceeds * self.fee_rate
                    capital += proceeds - fee
                    trades.append({
                        "date": current_date, "side": "sell",
                        "price": sell_price, "amount": proceeds,
                        "pnl_pct": loss_pct * 100, "reason": "손절",
                    })
                    position = 0
                    entry_price = 0
                elif loss_pct >= 0.05:  # 5% 익절
                    sell_price = current_price * (1 - self.slippage)
                    proceeds = position * sell_price
                    fee = proceeds * self.fee_rate
                    capital += proceeds - fee
                    trades.append({
                        "date": current_date, "side": "sell",
                        "price": sell_price, "amount": proceeds,
                        "pnl_pct": loss_pct * 100, "reason": "익절",
                    })
                    position = 0
                    entry_price = 0

        # 미청산 포지션 정리
        if position > 0:
            last_price = df.iloc[-1]["close"]
            capital += position * last_price * (1 - self.fee_rate)
            position = 0

        final_capital = capital
        return self._calculate_result(ticker, final_capital, equity_curve, trades)

    def _calculate_result(self, ticker: str, final_capital: float,
                          equity_curve: list, trades: list) -> BacktestResult:
        total_return = (final_capital / self.initial_capital - 1) * 100

        # 최대 낙폭
        values = [e["value"] for e in equity_curve]
        max_dd = 0.0
        peak = values[0] if values else self.initial_capital
        for v in values:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100
            max_dd = max(max_dd, dd)

        # 승률
        sell_trades = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sell_trades if t.get("pnl_pct", 0) > 0]
        win_rate = (len(wins) / len(sell_trades) * 100) if sell_trades else 0

        # 수익 팩터
        gross_profit = sum(t.get("pnl_pct", 0) for t in wins)
        losses = [t for t in sell_trades if t.get("pnl_pct", 0) <= 0]
        gross_loss = abs(sum(t.get("pnl_pct", 0) for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # 샤프 비율 (일간 수익률 기준)
        if len(values) > 1:
            returns = pd.Series(values).pct_change().dropna()
            sharpe = (returns.mean() / returns.std() * np.sqrt(365)) if returns.std() > 0 else 0
        else:
            sharpe = 0

        return BacktestResult(
            ticker=ticker,
            strategy_name=self.strategy.name,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(sell_trades),
            equity_curve=equity_curve,
            trades=trades,
        )

    def _empty_result(self, ticker: str) -> BacktestResult:
        return BacktestResult(
            ticker=ticker,
            strategy_name=self.strategy.name,
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return_pct=0, max_drawdown_pct=0, sharpe_ratio=0,
            win_rate=0, profit_factor=0, total_trades=0,
        )
