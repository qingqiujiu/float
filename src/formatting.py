def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_cost(amount: float) -> str:
    return f"¥{amount:.2f}"


def format_balance(amount: float) -> str:
    return f"¥{amount:.2f}"
