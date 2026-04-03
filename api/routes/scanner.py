from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from api.deps import get_engine

router = APIRouter(prefix="/api", tags=["scanner"])


@router.get("/scanner")
def get_scanner(engine=Depends(get_engine), _: str = Depends(verify_api_key)):
    """봇 엔진이 마지막으로 분석한 50코인 신호 캐시를 반환.

    API 호출 0회. 봇의 _check_entries()가 매 틱마다 갱신한 캐시를 그대로 읽음.
    이전 방식(API에서 직접 50코인 스캔)은 Upbit 레이트 리밋을 폭발시켜
    봇 거래를 중단시키는 버그가 있었음.
    """
    return engine._last_scan_results or []
