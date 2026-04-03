import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.auth import get_api_key, _dev_mode
from api.event_bus import event_bus

router = APIRouter()

HEARTBEAT_INTERVAL = 30  # 초


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket, key: str = Query(None)):
    # 인증 확인
    if not _dev_mode and (not key or key != get_api_key()):
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await websocket.accept()
    queue = event_bus.subscribe()

    try:
        # heartbeat + 이벤트 수신을 동시에 처리
        heartbeat_task = asyncio.create_task(_heartbeat(websocket))
        event_task = asyncio.create_task(_send_events(websocket, queue))

        # 클라이언트 메시지 수신 (ping/pong, 연결 유지)
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=HEARTBEAT_INTERVAL * 2
                )
                # 클라이언트 ping에 pong 응답
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # 클라이언트가 응답 없으면 연결 종료
                break
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        event_task.cancel()
        event_bus.unsubscribe(queue)


async def _heartbeat(websocket: WebSocket):
    """서버 → 클라이언트 heartbeat ping."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except Exception:
        pass


async def _send_events(websocket: WebSocket, queue: asyncio.Queue):
    """이벤트 큐에서 이벤트를 꺼내 클라이언트에 전송."""
    try:
        while True:
            event = await queue.get()
            await websocket.send_text(json.dumps(event, default=str))
    except Exception:
        pass
