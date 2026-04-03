import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ExchangeConfig(BaseModel):
    access_key: str = ""
    secret_key: str = ""


class TelegramConfig(BaseModel):
    enabled: bool = True
    token: str = ""
    chat_id: str = ""


class StrategyWeights(BaseModel):
    volatility_breakout: float = 0.35
    rsi_bollinger: float = 0.25
    ma_crossover: float = 0.20
    momentum_mtf: float = 0.20


class RiskConfig(BaseModel):
    max_position_pct: float = 0.20
    max_portfolio_coins: int = 10
    daily_loss_limit_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.05
    trailing_stop_pct: float = 0.02
    use_kelly: bool = True
    kelly_fraction: float = 0.5
    max_hold_minutes: int = 30
    time_stop_hours: int = 24
    circuit_breaker_pct: float = 0.05
    circuit_breaker_hours: int = 48


class CoinSelectionConfig(BaseModel):
    market: str = "KRW"
    min_volume_krw: float = 1_000_000_000  # 10억으로 낮춤 (더 많은 코인 관찰)
    max_coins_to_screen: int = 50          # 50개로 확대
    excluded_coins: list[str] = Field(default_factory=lambda: ["KRW-USDT", "KRW-USDC"])


class VolatilityBreakoutConfig(BaseModel):
    default_k: float = 0.5
    use_dynamic_k: bool = True
    noise_filter: bool = True
    lookback_days: int = 10


class RSIBollingerConfig(BaseModel):
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    bb_period: int = 20
    bb_std: float = 2.0
    volume_multiplier: float = 1.5


class MACrossoverConfig(BaseModel):
    fast_period: int = 5
    slow_period: int = 20
    volume_multiplier: float = 2.0
    adx_threshold: int = 25


class MomentumMTFConfig(BaseModel):
    timeframes: list[str] = Field(default_factory=lambda: ["minute240", "minute60", "minute15"])
    rsi_period: int = 14


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "data/logs/trading_bot.log"
    max_bytes: int = 10_485_760
    backup_count: int = 5


class BotConfig(BaseModel):
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    investment_krw: float = 2_000_000
    check_interval_seconds: int = 10
    dry_run: bool = False
    target_coins: list[str] = Field(default_factory=list)  # 빈 리스트면 자동 선정
    strategy_weights: StrategyWeights = Field(default_factory=StrategyWeights)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    coin_selection: CoinSelectionConfig = Field(default_factory=CoinSelectionConfig)
    volatility_breakout: VolatilityBreakoutConfig = Field(default_factory=VolatilityBreakoutConfig)
    rsi_bollinger: RSIBollingerConfig = Field(default_factory=RSIBollingerConfig)
    ma_crossover: MACrossoverConfig = Field(default_factory=MACrossoverConfig)
    momentum_mtf: MomentumMTFConfig = Field(default_factory=MomentumMTFConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(config_path: str = "config.yaml") -> BotConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {config_path}\n"
            f"config.example.yaml을 config.yaml로 복사한 후 API 키를 입력하세요."
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # 환경변수 우선 적용
    if os.getenv("UPBIT_ACCESS_KEY"):
        raw.setdefault("exchange", {})["access_key"] = os.getenv("UPBIT_ACCESS_KEY")
    if os.getenv("UPBIT_SECRET_KEY"):
        raw.setdefault("exchange", {})["secret_key"] = os.getenv("UPBIT_SECRET_KEY")
    if os.getenv("TELEGRAM_TOKEN"):
        raw.setdefault("telegram", {})["token"] = os.getenv("TELEGRAM_TOKEN")
    if os.getenv("TELEGRAM_CHAT_ID"):
        raw.setdefault("telegram", {})["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")

    return BotConfig(**raw)
