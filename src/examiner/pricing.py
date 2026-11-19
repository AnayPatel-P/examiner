"""Model prices (USD per million tokens, Anthropic list prices 2026-11)."""

from inspect_ai.model import ModelCost, ModelUsage

PRICES: dict[str, ModelCost] = {
    "anthropic/claude-sonnet-5-5": ModelCost(
        input=2.0, output=10.0, input_cache_write=2.5, input_cache_read=0.10
    ),
    "anthropic/claude-haiku-5-5": ModelCost(
        input=0.10, output=0.50, input_cache_write=0.125, input_cache_read=0.01
    ),
}


def usage_cost(usage: ModelUsage, price: ModelCost) -> float:
    return (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + (usage.input_tokens_cache_write or 0) * price.input_cache_write
        + (usage.input_tokens_cache_read or 0) * price.input_cache_read
    ) / 1_000_000
