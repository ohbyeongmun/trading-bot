import pandas as pd
import ta


def add_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    return ta.momentum.RSIIndicator(close=df[column], window=period).rsi()


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0,
                        column: str = "close") -> tuple[pd.Series, pd.Series, pd.Series]:
    bb = ta.volatility.BollingerBands(close=df[column], window=period, window_dev=std)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def add_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    return ta.trend.EMAIndicator(close=df[column], window=period).ema_indicator()


def add_sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    return ta.trend.SMAIndicator(close=df[column], window=period).sma_indicator()


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
             column: str = "close") -> tuple[pd.Series, pd.Series, pd.Series]:
    macd = ta.trend.MACD(close=df[column], window_fast=fast, window_slow=slow, window_sign=signal)
    return macd.macd(), macd.macd_signal(), macd.macd_diff()


def add_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return ta.trend.ADXIndicator(
        high=df["high"], low=df["low"], close=df["close"], window=period
    ).adx()


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=period
    ).average_true_range()


def add_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return df["volume"].rolling(window=period).mean()


def calculate_noise_ratio(df: pd.DataFrame) -> pd.Series:
    """노이즈 비율: 1 - abs(close - open) / (high - low)
    높을수록 횡보장 (변동성 돌파에 불리)"""
    body = abs(df["close"] - df["open"])
    wick = df["high"] - df["low"]
    return 1 - (body / wick.replace(0, float("nan")))


def calculate_volatility(df: pd.DataFrame, period: int = 7) -> float:
    """최근 N일 평균 변동률: (high - low) / close"""
    recent = df.tail(period)
    daily_range = (recent["high"] - recent["low"]) / recent["close"]
    return daily_range.mean()


def detect_market_regime(df: pd.DataFrame, period: int = 20) -> str:
    """시장 상태 감지: 'bull', 'bear', 'sideways'.

    EMA20 기울기 + 현재가 위치로 판단.
    """
    if len(df) < period + 5:
        return "sideways"

    ema = add_ema(df, period)
    current_price = df.iloc[-1]["close"]
    curr_ema = ema.iloc[-1]
    prev_ema = ema.iloc[-5]

    if pd.isna(curr_ema) or pd.isna(prev_ema):
        return "sideways"

    ema_slope = (curr_ema - prev_ema) / prev_ema
    price_vs_ema = (current_price - curr_ema) / curr_ema

    if ema_slope > 0.01 and price_vs_ema > 0.01:
        return "bull"
    elif ema_slope < -0.01 and price_vs_ema < -0.01:
        return "bear"
    return "sideways"
