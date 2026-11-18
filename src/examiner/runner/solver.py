"""Inspect solver that drives an external HTTP chat target."""

import httpx
from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageUser, ModelOutput
from inspect_ai.solver import Generate, Solver, TaskState, solver


def transcript_text(messages: list[ChatMessage]) -> str:
    label = {"user": "USER", "assistant": "BOT"}
    return "\n".join(
        f"{label[m.role]}: {m.text}" for m in messages if m.role in ("user", "assistant")
    )


@solver
def http_target(url: str, variant: str = "naive", timeout: float = 60.0) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        turns: list[str] = state.metadata["scenario"]["turns"]
        state.messages = []
        reply = ""
        async with httpx.AsyncClient(timeout=timeout) as client:
            for turn in turns:
                state.messages.append(ChatMessageUser(content=turn))
                history = [
                    {"role": m.role, "content": m.text}
                    for m in state.messages
                    if m.role in ("user", "assistant")
                ]
                try:
                    resp = await client.post(
                        f"{url.rstrip('/')}/chat",
                        json={"variant": variant, "messages": history},
                    )
                    resp.raise_for_status()
                    reply = resp.json()["reply"]
                except (httpx.HTTPError, KeyError, ValueError) as e:
                    raise RuntimeError(f"target error: {type(e).__name__}: {e}") from e
                state.messages.append(ChatMessageAssistant(content=reply))
        state.output = ModelOutput.from_content(f"meridian/{variant}", reply)
        return state

    return solve
