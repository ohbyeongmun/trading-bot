"""Upbit 코인 트레이딩봇 - 메인 진입점."""

import sys
from pathlib import Path

from bot.core.config import load_config
from bot.utils.logger import setup_logger, get_logger


def main():
    # 설정 로드
    config_path = "config.yaml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"오류: {e}")
        print("config.example.yaml을 config.yaml로 복사하고 API 키를 입력하세요:")
        print("  cp config.example.yaml config.yaml")
        sys.exit(1)

    # 로깅 설정
    setup_logger(config.logging)
    logger = get_logger("trading_bot")

    # API 키 확인
    if not config.exchange.access_key or config.exchange.access_key == "YOUR_UPBIT_ACCESS_KEY":
        logger.error("Upbit API 키가 설정되지 않았습니다. config.yaml을 확인하세요.")
        sys.exit(1)

    # data 디렉토리 생성
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    # 엔진 시작
    from bot.core.engine import TradingEngine
    engine = TradingEngine(config)

    try:
        engine.start()
    except KeyboardInterrupt:
        engine.shutdown()
    except Exception as e:
        logger.critical(f"치명적 오류: {e}", exc_info=True)
        engine.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
