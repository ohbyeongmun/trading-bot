import os
import secrets

from fastapi import HTTPException, Security, Query
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# API 키: 환경변수 또는 자동 생성
_api_key = os.environ.get("TRADING_API_KEY") or secrets.token_urlsafe(32)

# 개발 모드: TRADING_PROD=1 이 아니면 인증 건너뜀 (기본 dev)
_dev_mode = os.environ.get("TRADING_PROD", "").strip() not in ("1", "true", "yes")


def get_api_key() -> str:
    """현재 API 키 반환 (시작 시 로그에 출력용)."""
    return _api_key


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """REST API 인증. X-API-Key 헤더 확인."""
    if _dev_mode:
        return "dev"
    if not api_key or api_key != _api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def verify_ws_api_key(key: str = Query(None)) -> str:
    """WebSocket 인증. ?key= 쿼리 파라미터 확인."""
    if _dev_mode:
        return "dev"
    if not key or key != _api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key
