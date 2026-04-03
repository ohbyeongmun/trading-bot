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

    async def send_loop():
        """이벤트 큐 + heartbeat을 클라이언트에 전송."""
        heartbeat_counter = 0
        while True:
            try:
                # 이벤트가 있으면 전송, 없으면 heartbeat 간격만큼 대기
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                await websocket.send_text(json.dumps(event, default=str))
            except asyncio.TimeoutError:
                # 이벤트 없으면 heartbeat 전송
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break

    async def recv_loop():
        """클라이언트 메시지 수신 (ping 응답, 연결 유지 확인)."""
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception:
                break

    try:
        # 송신/수신을 병렬 실행, 하나라도 끝나면 둘 다 종료
        send_task = asyncio.create_task(send_loop())
        recv_task = asyncio.create_task(recv_loop())
        done, pending = await asyncio.wait(
            [send_task, recv_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except Exception:
        pass
    finally:
        event_bus.unsubscribe(queue)
