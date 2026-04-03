from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from bot.strategy.base import Signal

router = APIRouter(prefix="/api", tags=["scanner"])


@router.get("/scanner")
def get_scanner(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    """50개 관찰 코인의 실시간 신호/지표 스캔 결과."""
    if not engine.target_coins:
        return []

    results = []
    tickers = engine.target_coins
    prices = engine.client.get_current_prices(tickers)

    # 보유 중인 코인
    open_positions = engine.db.get_open_positions()
    held = {p.ticker: p for p in open_positions}

    for ticker in tickers:
        current_price = prices.get(ticker)
        if not current_price:
            continue

        try:
            # 각 전략 분석
            strategy_results = {}
            for name, strategy in engine.strategies.items():
                interval = strategy.get_preferred_interval()
                candle_count = strategy.get_required_candle_count()
                df = engine.client.get_ohlcv(ticker, interval, candle_count)
                if df is None or len(df) < candle_count // 2:
                    continue

                kwargs = {"current_price": current_price}
                if name == "momentum_mtf":
                    ohlcv_map = {}
                    for tf in strategy.timeframes:
                        tf_df = engine.client.get_ohlcv(ticker, tf, 50)
                        if tf_df is not None:
                            ohlcv_map[tf] = tf_df
                    kwargs["ohlcv_by_timeframe"] = ohlcv_map

                result = strategy.analyze(ticker, df, **kwargs)
                strategy_results[name] = result

            if not strategy_results:
                continue

            # 앵상블 결과
            ensemble = engine.ensemble.evaluate(ticker, strategy_results)

            # 기본 지표 (15분봉 기준)
            df_15m = engine.client.get_ohlcv(ticker, "minute15", 30)
            rsi_val = None
            bb_pos = None
            vol_ratio = None
            change_24h = None

            if df_15m is not None and len(df_15m) >= 20:
                from bot.analysis.indicators import add_rsi, add_bollinger_bands, add_volume_sma
                rsi = add_rsi(df_15m, 14)
                rsi_val = round(rsi.iloc[-1], 1) if not rsi.iloc[-1] != rsi.iloc[-1] else None

                bb_upper, _, bb_lower = add_bollinger_bands(df_15m, 20, 2.0)
                if bb_upper.iloc[-1] != bb_lower.iloc[-1]:
                    bb_pos = round((current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100, 1)

                vol_sma = add_volume_sma(df_15m, 20)
                if vol_sma.iloc[-1] > 0:
                    vol_ratio = round(df_15m.iloc[-1]["volume"] / vol_sma.iloc[-1], 2)

            # 24시간 변동률
            df_day = engine.client.get_ohlcv(ticker, "day", 2)
            if df_day is not None and len(df_day) >= 2:
                prev_close = df_day.iloc[-2]["close"]
                if prev_close > 0:
                    change_24h = round((current_price / prev_close - 1) * 100, 2)

            # 보유 여부
            position = held.get(ticker)
            pnl_pct = None
            if position:
                pnl_pct = round((current_price / position.entry_price - 1) * 100, 2)

            results.append({
                "ticker": ticker,
                "coin": ticker.replace("KRW-", ""),
                "price": current_price,
                "signal": ensemble.signal.name,
                "confidence": round(ensemble.confidence, 3),
                "score": round(ensemble.metadata.get("weighted_score", 0), 3),
                "rsi": rsi_val,
                "bb_position": bb_pos,
                "volume_ratio": vol_ratio,
                "change_24h": change_24h,
                "held": position is not None,
                "pnl_pct": pnl_pct,
                "strategies": {
                    name: {"signal": r.signal.name, "confidence": round(r.confidence, 2)}
                    for name, r in strategy_results.items()
                },
            })

        except Exception:
            continue

    # 신호 강도순 정렬 (BUY > NEUTRAL > SELL, confidence 내림차순)
    signal_order = {"STRONG_BUY": 0, "BUY": 1, "NEUTRAL": 2, "SELL": 3, "STRONG_SELL": 4}
    results.sort(key=lambda x: (signal_order.get(x["signal"], 2), -x["confidence"]))

    return results
