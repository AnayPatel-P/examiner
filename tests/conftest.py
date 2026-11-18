import socket
import threading
import time
from collections.abc import Awaitable, Callable, Iterator

import httpx
import pytest
import uvicorn

from examiner.meridian.app import create_app

ReplyFn = Callable[[str, list[dict]], Awaitable[str]]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class BotServer:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self.reply: Callable[[list[dict]], str] = lambda msgs: "Our overdraft fee is $34."

    async def responder(self, system: str, messages: list[dict]) -> str:
        self.calls.append(messages)
        return self.reply(messages)


@pytest.fixture
def bot() -> Iterator[tuple[str, BotServer]]:
    """A real Meridian app on a free port, with a scripted responder."""
    srv = BotServer()
    port = free_port()
    config = uvicorn.Config(create_app(srv.responder), port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(url + "/health")
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield url, srv
    server.should_exit = True
    thread.join(timeout=5)
