"""FastAPI + Trading Engine 통합 서버.

봇 엔진을 백그라운드 스레드로, FastAPI를 메인 스레드로 실행.
(async 전환 전 중간 단계. Phase 2 async 마이그레이션 후 단일 이벤트 루프로 통합.)
"""
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import get_api_key
from api.event_bus import event_bus
from api.routes import dashboard, trades, positions, strategies, daily_reports, bot_control
from api.websocket_handler import router as ws_router

from bot.core.config import load_config
from bot.core.engine import TradingEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 봇 엔진을 백그라운드 스레드로 실행."""
    api_key = get_api_key()
    print(f"\n{'='*50}")
    print(f"  Trading Bot API Server")
    print(f"  API Key: {api_key}")
    print(f"  Dashboard: http://localhost:3000")
    print(f"  API Docs: http://localhost:8000/docs")
    print(f"{'='*50}\n")

    config = load_config("config.yaml")
    engine = TradingEngine(config)
    engine.event_bus = event_bus

    # 엔진을 state에 먼저 등록 (API 요청이 엔진 참조 가능하도록)
    app.state.engine = engine

    # 봇 엔진을 백그라운드 스레드로 실행
    bot_thread = threading.Thread(target=engine.start, daemon=True, name="bot-engine")
    bot_thread.start()
    app.state.bot_thread = bot_thread

    yield  # 서버 실행 중

    # shutdown
    engine.shutdown()


app = FastAPI(
    title="Trading Bot API",
    description="Upbit 트레이딩봇 실시간 모니터링 API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: 로컬 Next.js 개발 서버 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_engine_ready(request: Request, call_next):
    """엔진 초기화 전 요청이 오면 503 반환. OPTIONS(CORS preflight)는 통과."""
    if (request.method != "OPTIONS"
            and request.url.path.startswith("/api/")
            and not hasattr(app.state, "engine")):
        return JSONResponse(
            status_code=503,
            content={"detail": "Bot engine is starting up, please wait..."},
        )
    return await call_next(request)


# 라우트 등록
app.include_router(dashboard.router)
app.include_router(trades.router)
app.include_router(positions.router)
app.include_router(strategies.router)
app.include_router(daily_reports.router)
app.include_router(bot_control.router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok", "subscribers": event_bus.subscriber_count}


def run():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run()
