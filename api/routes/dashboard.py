from datetime import date, timedelta

from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import DashboardResponse

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    db = engine.db

    total_balance = engine.portfolio.get_total_balance()
    today = date.today()

    daily_report = db.get_daily_report(today)
    daily_pnl = daily_report.pnl if daily_report else 0
    daily_pnl_pct = daily_report.pnl_pct if daily_report else 0

    weekly_pnl_pct = _calc_period_pnl(db, today - timedelta(days=7), today)
    monthly_pnl_pct = _calc_period_pnl(db, today - timedelta(days=30), today)

    open_positions = len(db.get_open_positions())

    bot_status = "running"

    return DashboardResponse(
        total_balance=total_balance,
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        weekly_pnl_pct=weekly_pnl_pct,
        monthly_pnl_pct=monthly_pnl_pct,
        open_positions=open_positions,
        bot_status=bot_status,
        market_regime=engine._market_regime,
    )


def _calc_period_pnl(db, start_date: date, end_date: date) -> float:
    reports = db.get_daily_reports_range(start_date, end_date)
    if not reports:
        return 0.0
    first_balance = reports[0].starting_balance
    if first_balance <= 0:
        return 0.0
    total_pnl = sum(r.pnl for r in reports)
    return (total_pnl / first_balance) * 100
