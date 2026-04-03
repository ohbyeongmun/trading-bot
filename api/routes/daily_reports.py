from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import DailyReportResponse

router = APIRouter(prefix="/api", tags=["daily_reports"])


@router.get("/daily-reports", response_model=list[DailyReportResponse])
def get_daily_reports(
    engine=Depends(get_engine),
    limit: int = Query(30, ge=1, le=365),
    _: str = Depends(verify_api_key),
):
    reports = engine.db.get_recent_daily_reports(limit)
    return [
        DailyReportResponse(
            date=r.date, starting_balance=r.starting_balance,
            ending_balance=r.ending_balance, pnl=r.pnl, pnl_pct=r.pnl_pct,
            trades_count=r.trades_count, win_rate=r.win_rate,
            max_drawdown=r.max_drawdown,
        )
        for r in reports
    ]
