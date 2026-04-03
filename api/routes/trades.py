from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import TradeResponse

router = APIRouter(prefix="/api", tags=["trades"])


@router.get("/trades", response_model=list[TradeResponse])
def get_trades(
    engine=Depends(get_engine),
    strategy: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key),
):
    trades = engine.db.get_trades_filtered(
        strategy=strategy, ticker=ticker, limit=limit, offset=offset
    )
    return [
        TradeResponse(
            id=t.id, ticker=t.ticker, side=t.side, amount_krw=t.amount_krw,
            volume=t.volume, price=t.price, strategy=t.strategy,
            confidence=t.confidence, reason=t.reason or "", fee=t.fee,
            timestamp=t.timestamp,
        )
        for t in trades
    ]
