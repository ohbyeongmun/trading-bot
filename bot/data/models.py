from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # 'buy' or 'sell'
    amount_krw = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    strategy = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    reason = Column(String, default="")
    fee = Column(Float, default=0.0)
    order_uuid = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    amount_krw = Column(Float, nullable=False)
    entry_time = Column(DateTime, default=datetime.utcnow)
    strategy = Column(String, nullable=False)
    highest_price = Column(Float, nullable=False)
    status = Column(String, default="open", index=True)  # 'open', 'closed'
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    trades_count = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    best_trade = Column(String, default="")
    worst_trade = Column(String, default="")


def create_db_engine(db_path: str = "data/trading_bot.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return engine


def create_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
