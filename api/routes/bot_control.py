from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import BotStatusResponse

router = APIRouter(prefix="/api", tags=["bot_control"])


@router.get("/bot/status", response_model=BotStatusResponse)
def bot_status(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    status = "paused" if engine.risk_manager.is_trading_paused else "running"
    return BotStatusResponse(status=status, message="24시간 자동 운영 중")
