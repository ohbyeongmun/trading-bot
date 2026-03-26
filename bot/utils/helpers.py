from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def format_krw(amount: float) -> str:
    if amount >= 1_000_000:
        return f"{amount:,.0f}원"
    return f"{amount:,.2f}원"


def format_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def ticker_to_symbol(ticker: str) -> str:
    """KRW-BTC -> BTC"""
    return ticker.replace("KRW-", "")


def symbol_to_ticker(symbol: str) -> str:
    """BTC -> KRW-BTC"""
    if symbol.startswith("KRW-"):
        return symbol
    return f"KRW-{symbol}"
