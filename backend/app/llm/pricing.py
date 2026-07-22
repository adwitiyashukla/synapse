"""Token pricing per model, in USD per one million tokens.

Prices verified July 2026. Update this table as providers change pricing;
unknown models simply report zero cost rather than failing.
"""

PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    # model: (input, output)
    "gpt-5.6-sol": (5.00, 30.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated cost in USD for a request."""
    input_price, output_price = PRICES_PER_MILLION.get(model, (0.0, 0.0))
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return round(cost, 8)
