from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import PositionResponse

router = APIRouter(prefix="/api", tags=["positions"])


@router.get("/positions", response_model=list[PositionResponse])
def get_positions(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    positions = engine.db.get_open_positions()
    tickers = [p.ticker for p in positions]
    prices = engine.client.get_current_prices(tickers) if tickers else {}

    result = []
    for p in positions:
        current_price = prices.get(p.ticker)
        pnl_pct = None
        if current_price and p.entry_price > 0:
            pnl_pct = (current_price / p.entry_price - 1) * 100
        result.append(PositionResponse(
            id=p.id, ticker=p.ticker, entry_price=p.entry_price,
            volume=p.volume, amount_krw=p.amount_krw, strategy=p.strategy,
            entry_time=p.entry_time, highest_price=p.highest_price,
            current_price=current_price, pnl_pct=pnl_pct,
        ))
    return result
