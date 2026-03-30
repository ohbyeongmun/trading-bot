from bot.strategy.base import BaseStrategy, StrategyResult, Signal
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# 매수 임계값: 가중 점수가 이 값 이상이면 매수 신호
BUY_THRESHOLD = 0.15
STRONG_BUY_THRESHOLD = 0.5
SELL_THRESHOLD = -0.2


class EnsembleStrategy:
    """여러 전략의 신호를 가중 평균으로 결합."""

    def __init__(self, strategies: list[BaseStrategy], weights: dict[str, float]):
        self.strategies = {s.name: s for s in strategies}
        self.weights = weights
        total = sum(weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in weights.items()}

    def evaluate(self, ticker: str, results: dict[str, StrategyResult]) -> StrategyResult:
        """각 전략 결과를 가중 합산하여 최종 신호 생성."""
        if not results:
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "전략 결과 없음")

        weighted_score = 0.0
        total_weight = 0.0
        reasons = []

        for strategy_name, result in results.items():
            weight = self.weights.get(strategy_name, 0.0)
            if weight <= 0:
                continue

            score = result.signal.value * result.confidence
            weighted_score += score * weight
            total_weight += weight

            if result.signal != Signal.NEUTRAL:
                reasons.append(f"{strategy_name}: {result.signal.name}({result.confidence:.2f})")

        if total_weight <= 0:
            return StrategyResult(Signal.NEUTRAL, 0.0, ticker, "가중치 합계 0")

        normalized_score = weighted_score / total_weight
        confidence = abs(normalized_score)

        # 신호 결정
        if normalized_score >= STRONG_BUY_THRESHOLD:
            signal = Signal.STRONG_BUY
        elif normalized_score >= BUY_THRESHOLD:
            signal = Signal.BUY
        elif normalized_score <= SELL_THRESHOLD:
            signal = Signal.SELL if normalized_score > -STRONG_BUY_THRESHOLD else Signal.STRONG_SELL
        else:
            signal = Signal.NEUTRAL

        reason = " | ".join(reasons) if reasons else "신호 없음"
        metadata = {
            "weighted_score": normalized_score,
            "individual_results": {k: v.signal.name for k, v in results.items()},
        }

        logger.debug(f"[앙상블] {ticker}: score={normalized_score:.3f} -> {signal.name}")
        return StrategyResult(signal, confidence, ticker, reason, metadata)
