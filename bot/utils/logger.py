import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from bot.core.config import LoggingConfig


def setup_logger(config: LoggingConfig) -> logging.Logger:
    logger = logging.getLogger("trading_bot")
    logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 파일 핸들러
    log_path = Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "trading_bot") -> logging.Logger:
    return logging.getLogger(name)
