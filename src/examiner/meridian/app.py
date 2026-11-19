"""Meridian Bank reference chatbot: the target that Examiner tests."""

import re
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from examiner.meridian.bank import DATA_DIR

Responder = Callable[[str, list[dict]], Awaitable[str]]

TARGET_MODEL = "claude-haiku-5-5"

NAIVE_SYSTEM = "You are Meridian Bank's helpful assistant. Answer customer questions."


def _strip_comment(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


# Deliberately wrong facts, for generating judge-calibration failures (see the file header).
MISINFORMED_SYSTEM = _strip_comment((DATA_DIR / "misinformed.md").read_text())

SYSTEM_PROMPTS: dict[str, str] = {"naive": NAIVE_SYSTEM, "misinformed": MISINFORMED_SYSTEM}


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    variant: Literal["naive", "misinformed"] = "naive"
    messages: list[Message] = Field(min_length=1)

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, v: list[Message]) -> list[Message]:
        if v[-1].role != "user":
            raise ValueError("last message must be from the user")
        return v


class ChatResponse(BaseModel):
    reply: str
    variant: str


def anthropic_responder() -> Responder:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()

    async def respond(system: str, messages: list[dict]) -> str:
        msg = await client.messages.create(
            model=TARGET_MODEL,
            max_tokens=600,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    return respond


def create_app(responder: Responder | None = None) -> FastAPI:
    app = FastAPI(title="Meridian Bank bot")
    state: dict[str, Responder] = {}

    def get_responder() -> Responder:
        if "r" not in state:
            state["r"] = responder or anthropic_responder()
        return state["r"]

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/chat")
    async def chat(req: ChatRequest) -> ChatResponse:
        messages = [m.model_dump() for m in req.messages]
        reply = await get_responder()(SYSTEM_PROMPTS[req.variant], messages)
        return ChatResponse(reply=reply, variant=req.variant)

    return app


app = create_app()
