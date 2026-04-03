"""공통 의존성. 모든 라우트에서 사용."""
from fastapi import Request, HTTPException


def get_engine(request: Request):
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Bot engine is starting up")
    return engine
