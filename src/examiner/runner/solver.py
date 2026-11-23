"""Inspect solver that drives an external HTTP chat target."""

import time

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
        usage: dict[str, int] | None = {"input_tokens": 0, "output_tokens": 0}
        latency = 0.0  # seconds spent waiting on the target, summed over turns
        async with httpx.AsyncClient(timeout=timeout) as client:
            for turn in turns:
                state.messages.append(ChatMessageUser(content=turn))
                history = [
                    {"role": m.role, "content": m.text}
                    for m in state.messages
                    if m.role in ("user", "assistant")
                ]
                try:
                    t0 = time.perf_counter()
                    resp = await client.post(
                        f"{url.rstrip('/')}/chat",
                        json={"variant": variant, "messages": history},
                    )
                    latency += time.perf_counter() - t0
                    resp.raise_for_status()
                    body = resp.json()
                    reply = body["reply"]
                    turn_usage = body.get("usage")
                    if not str(reply).strip():
                        raise ValueError("empty reply")
                except (httpx.HTTPError, KeyError, ValueError) as e:
                    raise RuntimeError(f"target error: {type(e).__name__}: {e}") from e
                counts = turn_usage if isinstance(turn_usage, dict) else {}
                if usage is not None and all(isinstance(counts.get(k), int) for k in usage):
                    for k in usage:
                        usage[k] += counts[k]
                else:
                    usage = None  # missing or malformed usage from the target: cost unknown
                state.messages.append(ChatMessageAssistant(content=reply))
        state.metadata["target_usage"] = usage
        state.metadata["target_latency_s"] = round(latency, 3)
        state.output = ModelOutput.from_content(f"meridian/{variant}", reply)
        return state

    return solve
