"""백테스트 실행 스크립트.

사용법:
    python scripts/backtest_runner.py
    python scripts/backtest_runner.py --ticker KRW-BTC --days 180
    python scripts/backtest_runner.py --top 10
"""

import sys
import argparse
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.backtest.data_loader import DataLoader
from bot.backtest.backtester import Backtester
from bot.backtest.report import format_report
from bot.strategy.volatility_breakout import VolatilityBreakoutStrategy
from bot.strategy.rsi_bollinger import RSIBollingerStrategy
from bot.strategy.ma_crossover import MACrossoverStrategy


def main():
    parser = argparse.ArgumentParser(description="트레이딩 전략 백테스트")
    parser.add_argument("--ticker", type=str, help="특정 코인 (예: KRW-BTC)")
    parser.add_argument("--days", type=int, default=180, help="백테스트 기간 (일)")
    parser.add_argument("--capital", type=float, default=2_000_000, help="초기 자본금")
    parser.add_argument("--top", type=int, default=5, help="상위 N개 코인 백테스트")
    args = parser.parse_args()

    loader = DataLoader()
    strategies = [
        VolatilityBreakoutStrategy(),
        RSIBollingerStrategy(),
        MACrossoverStrategy(),
    ]

    # 대상 코인 결정
    if args.ticker:
        tickers = [args.ticker]
    else:
        print(f"거래량 상위 {args.top}개 코인 선정 중...")
        all_tickers = loader.get_available_tickers()
        # 간단하게 상위 코인 선택 (거래대금 기반)
        scored = []
        for t in all_tickers[:50]:
            df = loader.load_ohlcv(t, "day", 7)
            if df is not None and len(df) >= 3:
                avg_vol = (df["close"] * df["volume"]).mean()
                scored.append((t, avg_vol))
        scored.sort(key=lambda x: x[1], reverse=True)
        tickers = [t for t, _ in scored[:args.top]]

    print(f"대상 코인: {tickers}")
    print(f"기간: {args.days}일 | 자본금: {args.capital:,.0f}원")
    print()

    all_results = []

    for ticker in tickers:
        print(f"\n--- {ticker} 데이터 로드 ---")
        df = loader.load_extended_ohlcv(ticker, "day", args.days)
        if df is None:
            print(f"  {ticker}: 데이터 로드 실패")
            continue
        print(f"  로드 완료: {len(df)}일")

        for strategy in strategies:
            bt = Backtester(strategy, args.capital)
            result = bt.run(ticker, df)
            all_results.append(result)
            print(f"  {strategy.name}: {result.total_return_pct:+.2f}% "
                  f"(MDD: {result.max_drawdown_pct:.2f}%, 거래: {result.total_trades}건)")

    print("\n")
    print(format_report(all_results))


if __name__ == "__main__":
    main()
