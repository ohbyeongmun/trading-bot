from bot.backtest.backtester import BacktestResult


def format_report(results: list[BacktestResult]) -> str:
    """여러 백테스트 결과를 표 형식으로 포맷."""
    if not results:
        return "백테스트 결과 없음"

    lines = []
    lines.append("=" * 80)
    lines.append("백테스트 종합 결과")
    lines.append("=" * 80)
    lines.append(
        f"{'티커':<12} {'전략':<22} {'수익률':>8} {'MDD':>8} "
        f"{'샤프':>6} {'승률':>6} {'거래수':>6}"
    )
    lines.append("-" * 80)

    for r in results:
        lines.append(
            f"{r.ticker:<12} {r.strategy_name:<22} {r.total_return_pct:>+7.2f}% "
            f"{r.max_drawdown_pct:>7.2f}% {r.sharpe_ratio:>6.2f} "
            f"{r.win_rate:>5.1f}% {r.total_trades:>6d}"
        )

    lines.append("-" * 80)

    # 평균
    if len(results) > 1:
        avg_return = sum(r.total_return_pct for r in results) / len(results)
        avg_mdd = sum(r.max_drawdown_pct for r in results) / len(results)
        avg_sharpe = sum(r.sharpe_ratio for r in results) / len(results)
        avg_wr = sum(r.win_rate for r in results) / len(results)
        total_trades = sum(r.total_trades for r in results)
        lines.append(
            f"{'평균':<12} {'':22} {avg_return:>+7.2f}% "
            f"{avg_mdd:>7.2f}% {avg_sharpe:>6.2f} "
            f"{avg_wr:>5.1f}% {total_trades:>6d}"
        )

    lines.append("=" * 80)
    return "\n".join(lines)
