import asyncio
import threading


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
        subscription = (asyncio.get_running_loop(), asyncio.Queue())
        with self._lock:
            self._subscribers.add(subscription)
        return subscription

    def unsubscribe(self, subscription) -> None:
        with self._lock:
            self._subscribers.discard(subscription)

    def publish(self, event: str, payload: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            if not loop.is_closed():
                loop.call_soon_threadsafe(queue.put_nowait, (event, payload))


broker = EventBroker()
