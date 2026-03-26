from bot.exchange.upbit_client import UpbitClient
from bot.core.config import RiskConfig
from bot.data.database import Database
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class PortfolioManager:
    """포트폴리오 레벨 관리: 잔고, 포지션, 분산."""

    def __init__(self, client: UpbitClient, config: RiskConfig, db: Database):
        self.client = client
        self.config = config
        self.db = db

    def get_total_balance(self) -> float:
        """전체 포트폴리오 가치 (KRW 잔고 + 보유 코인 평가액)."""
        krw = self.client.get_krw_balance()
        balances = self.client.get_balances()
        total = krw

        for b in balances:
            currency = b.get("currency", "")
            if currency == "KRW":
                continue
            balance = float(b.get("balance", 0))
            if balance <= 0:
                continue
            ticker = f"KRW-{currency}"
            price = self.client.get_current_price(ticker)
            if price:
                total += balance * price

        return total

    def get_available_krw(self) -> float:
        return self.client.get_krw_balance()

    def get_position_count(self) -> int:
        return len(self.db.get_open_positions())

    def get_position_value(self, ticker: str) -> float:
        """특정 코인 보유 평가액."""
        volume = self.client.get_balance(ticker)
        if volume <= 0:
            return 0.0
        price = self.client.get_current_price(ticker)
        return volume * price if price else 0.0

    def get_portfolio_allocation(self) -> dict[str, float]:
        """포트폴리오 내 각 코인의 비중."""
        total = self.get_total_balance()
        if total <= 0:
            return {}

        allocation = {"KRW": self.client.get_krw_balance() / total}
        balances = self.client.get_balances()

        for b in balances:
            currency = b.get("currency", "")
            if currency == "KRW":
                continue
            balance = float(b.get("balance", 0))
            if balance <= 0:
                continue
            ticker = f"KRW-{currency}"
            price = self.client.get_current_price(ticker)
            if price:
                allocation[ticker] = (balance * price) / total

        return allocation

    def check_concentration(self) -> list[str]:
        """과도한 집중 경고. 30% 이상 비중 코인 반환."""
        allocation = self.get_portfolio_allocation()
        warnings = []
        for ticker, pct in allocation.items():
            if ticker == "KRW":
                continue
            if pct > 0.30:
                warnings.append(f"{ticker}: {pct:.1%}")
                logger.warning(f"포트폴리오 집중 경고: {ticker} = {pct:.1%}")
        return warnings
