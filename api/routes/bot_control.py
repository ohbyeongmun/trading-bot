from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine
from api.schemas.responses import BotStatusResponse

router = APIRouter(prefix="/api", tags=["bot_control"])


@router.post("/bot/start", response_model=BotStatusResponse)
def start_bot(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    if engine.risk_manager._trading_paused:
        engine.risk_manager._trading_paused = False
        engine.risk_manager._pause_time = None
        engine.risk_manager._circuit_breaker_active = False
        return BotStatusResponse(status="running", message="거래 재개됨")
    return BotStatusResponse(status="running", message="이미 실행 중")


@router.post("/bot/stop", response_model=BotStatusResponse)
def stop_bot(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    engine.risk_manager._trading_paused = True
    return BotStatusResponse(status="stopped", message="거래 중지됨 (수동)")
