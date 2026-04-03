from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from api.deps import get_engine

router = APIRouter(prefix="/api", tags=["charts"])


@router.get("/ohlcv/{ticker}")
def get_ohlcv(
    ticker: str,
    interval: str = Query("minute15", regex="^(minute1|minute3|minute5|minute15|minute30|minute60|minute240|day|week)$"),
    count: int = Query(100, ge=1, le=500),
    engine=Depends(get_engine),
    _: str = Depends(verify_api_key),
):
    df = engine.client.get_ohlcv(ticker, interval=interval, count=count)
    if df is None:
        return []

    candles = []
    for idx, row in df.iterrows():
        candles.append({
            "time": int(idx.timestamp()),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
        })
    return candles


@router.get("/trades/{ticker}")
def get_ticker_trades(
    ticker: str,
    limit: int = Query(50, ge=1, le=200),
    engine=Depends(get_engine),
    _: str = Depends(verify_api_key),
):
    """특정 코인의 매수/매도 거래 마커 데이터."""
    trades = engine.db.get_trades_filtered(ticker=ticker, limit=limit)
    return [
        {
            "time": int(t.timestamp.timestamp()) if t.timestamp else 0,
            "position": "belowBar" if t.side == "buy" else "aboveBar",
            "color": "#10b981" if t.side == "buy" else "#ef4444",
            "shape": "arrowUp" if t.side == "buy" else "arrowDown",
            "text": f"{'매수' if t.side == 'buy' else '매도'} {t.price:,.0f}",
        }
        for t in trades
    ]
