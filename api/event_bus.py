import asyncio
from datetime import datetime
from typing import Any


class EventBus:
    """인메모리 이벤트 버스. asyncio.Queue 기반.

    봇 엔진이 publish() → WebSocket 핸들러가 subscribe()로 구독.
    여러 구독자를 지원 (각 WebSocket 클라이언트마다 독립 큐).
    """

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def publish(self, event_type: str, data: Any = None):
        """이벤트 발행. 동기 코드에서도 호출 가능."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        dead_queues = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for q in dead_queues:
            self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        """새 구독자 큐 생성. WebSocket 핸들러에서 호출."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """구독 해제."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_bus = EventBus()
