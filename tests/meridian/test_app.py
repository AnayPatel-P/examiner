from fastapi.testclient import TestClient

from examiner.meridian.app import create_app
from examiner.meridian.bank import load_faq, load_fee_schedule


class FakeResponder:
    def __init__(self, reply: str = "Hello from Meridian."):
        self.reply = reply
        self.calls: list[tuple[str, list[dict]]] = []

    async def __call__(self, system: str, messages: list[dict]) -> str:
        self.calls.append((system, messages))
        return self.reply


def client(responder: FakeResponder | None = None) -> TestClient:
    return TestClient(create_app(responder or FakeResponder()))


def test_chat_returns_reply():
    r = client().post(
        "/chat", json={"variant": "naive", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert r.status_code == 200
    assert r.json() == {"reply": "Hello from Meridian.", "variant": "naive"}


def test_chat_passes_history_in_order():
    fake = FakeResponder()
    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]
    client(fake).post("/chat", json={"variant": "naive", "messages": history})
    assert [m["content"] for m in fake.calls[0][1]] == ["one", "two", "three"]


def test_chat_rejects_unknown_variant():
    r = client().post(
        "/chat", json={"variant": "bogus", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert r.status_code == 422


def test_chat_rejects_empty_messages():
    r = client().post("/chat", json={"variant": "naive", "messages": []})
    assert r.status_code == 422


def test_chat_rejects_last_message_not_user():
    r = client().post(
        "/chat",
        json={"variant": "naive", "messages": [{"role": "assistant", "content": "hi"}]},
    )
    assert r.status_code == 422


def test_health():
    assert client().get("/health").json() == {"ok": True}


def test_fee_schedule_has_overdraft_34():
    fees = load_fee_schedule()
    assert fees["overdraft"]["fee_per_item_usd"] == 34
    assert "60 days" in load_faq()
