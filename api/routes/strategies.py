from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import StrategyStatsResponse

router = APIRouter(prefix="/api", tags=["strategies"])


@router.get("/strategies", response_model=list[StrategyStatsResponse])
def get_strategies(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    strategy_names = list(engine.strategies.keys()) + ["ensemble"]

    result = []
    for name in strategy_names:
        stats = engine.db.get_strategy_stats(name)
        result.append(StrategyStatsResponse(
            name=name,
            total_trades=stats.get("total_trades", 0),
            win_rate=stats.get("win_rate", 0.0),
            avg_profit_pct=stats.get("avg_win", 0.0) * 100,
            avg_loss_pct=stats.get("avg_loss", 0.0) * 100,
            total_pnl=stats.get("total_pnl", 0.0),
        ))
    return result
