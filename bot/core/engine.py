import time
from datetime import datetime

from bot.core.config import BotConfig
from bot.core.scheduler import Scheduler
from bot.exchange.upbit_client import UpbitClient
from bot.exchange.order_manager import OrderManager
from bot.strategy.base import Signal
from bot.strategy.volatility_breakout import VolatilityBreakoutStrategy
from bot.strategy.rsi_bollinger import RSIBollingerStrategy
from bot.strategy.ma_crossover import MACrossoverStrategy
from bot.strategy.momentum_mtf import MultiTimeframeMomentumStrategy
from bot.strategy.ensemble import EnsembleStrategy
from bot.analysis.coin_selector import CoinSelector
from bot.analysis.indicators import detect_market_regime
from bot.risk.risk_manager import RiskManager
from bot.risk.position_sizer import PositionSizer
from bot.risk.portfolio import PortfolioManager
from bot.data.database import Database
from bot.notify.telegram import TelegramNotifier
from bot.utils.helpers import now_kst, format_krw, format_pct
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TradingEngine:
    """트레이딩 봇 핵심 엔진."""

    def __init__(self, config: BotConfig):
        self.config = config

        # 거래소 클라이언트
        self.client = UpbitClient(config.exchange.access_key, config.exchange.secret_key)

        # 데이터베이스
        self.db = Database()

        # 텔레그램 알림
        self.notifier = TelegramNotifier(
            config.telegram.token, config.telegram.chat_id, config.telegram.enabled
        )

        # 리스크 관리
        self.risk_manager = RiskManager(config.risk, self.db, config.investment_krw)
        self.position_sizer = PositionSizer(config.risk)
        self.portfolio = PortfolioManager(self.client, config.risk, self.db)

        # 주문 관리
        self.order_manager = OrderManager(
            self.client, self.risk_manager, self.position_sizer,
            self.db, self.notifier, config.dry_run
        )

        # 코인 선정
        self.coin_selector = CoinSelector(self.client, config.coin_selection)

        # 전략 초기화
        self.strategies = self._init_strategies()
        self.ensemble = EnsembleStrategy(
            list(self.strategies.values()),
            {
                "volatility_breakout": config.strategy_weights.volatility_breakout,
                "rsi_bollinger": config.strategy_weights.rsi_bollinger,
                "ma_crossover": config.strategy_weights.ma_crossover,
                "momentum_mtf": config.strategy_weights.momentum_mtf,
            },
        )

        # 스케줄러
        self.scheduler = Scheduler()

        # 상태
        self.target_coins: list[str] = []
        self._starting_balance = 0.0
        self._market_regime = "sideways"

    def _init_strategies(self) -> dict:
        cfg = self.config
        return {
            "volatility_breakout": VolatilityBreakoutStrategy(
                default_k=cfg.volatility_breakout.default_k,
                use_dynamic_k=cfg.volatility_breakout.use_dynamic_k,
                noise_filter=cfg.volatility_breakout.noise_filter,
                lookback_days=cfg.volatility_breakout.lookback_days,
            ),
            "rsi_bollinger": RSIBollingerStrategy(
                rsi_period=cfg.rsi_bollinger.rsi_period,
                rsi_oversold=cfg.rsi_bollinger.rsi_oversold,
                rsi_overbought=cfg.rsi_bollinger.rsi_overbought,
                bb_period=cfg.rsi_bollinger.bb_period,
                bb_std=cfg.rsi_bollinger.bb_std,
                volume_multiplier=cfg.rsi_bollinger.volume_multiplier,
            ),
            "ma_crossover": MACrossoverStrategy(
                fast_period=cfg.ma_crossover.fast_period,
                slow_period=cfg.ma_crossover.slow_period,
                volume_multiplier=cfg.ma_crossover.volume_multiplier,
                adx_threshold=cfg.ma_crossover.adx_threshold,
            ),
            "momentum_mtf": MultiTimeframeMomentumStrategy(
                timeframes=cfg.momentum_mtf.timeframes,
                rsi_period=cfg.momentum_mtf.rsi_period,
            ),
        }

    def start(self):
        """봇 시작."""
        print("[봇] 엔진 시작 중...")
        logger.info("=" * 60)
        logger.info("트레이딩 봇 시작")
        logger.info(f"투자금: {format_krw(self.config.investment_krw)}")
        logger.info(f"Dry Run: {self.config.dry_run}")
        logger.info("=" * 60)

        # 초기 잔고 기록
        self._starting_balance = self.portfolio.get_total_balance()
        print(f"[봇] 현재 잔고: {format_krw(self._starting_balance)}")
        logger.info(f"현재 총 잔고: {format_krw(self._starting_balance)}")

        # 코인 선정 (config에 고정 코인이 있으면 바로 사용)
        if self.config.target_coins:
            self.target_coins = self.config.target_coins
            print(f"[봇] 고정 코인: {self.target_coins}")
        else:
            print("[봇] 코인 선정 중... (1~2분 소요)")
            self._refresh_coins()
            print(f"[봇] 선정 코인: {self.target_coins}")

        # 시장 상태 감지
        self._update_market_regime()
        print(f"[봇] 시장 상태: {self._market_regime}")

        # 알림
        strategy_names = list(self.strategies.keys())
        self.notifier.send_startup_sync(
            self._starting_balance, len(self.target_coins), strategy_names
        )

        # 스케줄러 설정
        self._setup_scheduler()

        print()
        print(f"[봇] 자동매매 시작! ({self.config.check_interval_seconds}초 간격)")
        print("[봇] 중지하려면 Ctrl+C")
        print("-" * 50)

        # 메인 루프 실행
        try:
            self.scheduler.run_loop(self.config.check_interval_seconds)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        logger.info("봇 종료 중...")
        self.notifier.send_alert_sync("봇이 종료되었습니다.")
        logger.info("봇 종료 완료")

    def _setup_scheduler(self):
        # 08:55 KST - 변동성 돌파 포지션 전량 매도
        self.scheduler.add_daily_event(8, 55, self._daily_sell_all, "일일 전량 매도")
        # 09:05 KST - 코인 재선정
        self.scheduler.add_daily_event(9, 5, self._daily_refresh, "코인 재선정")
        # 23:00 KST - 일일 리포트
        self.scheduler.add_daily_event(23, 0, self._daily_report, "일일 리포트")
        # 인터벌 콜백 - 매매 로직
        self.scheduler.add_interval_callback(self._trading_tick, "매매 체크")

    def _refresh_coins(self):
        logger.info("코인 선정 시작...")
        self.target_coins = self.coin_selector.get_tradeable_coins()
        logger.info(f"선정된 코인: {self.target_coins}")

    def _daily_sell_all(self):
        """08:55 KST - 변동성 돌파 전략 포지션 전량 매도."""
        logger.info("일일 리셋: 변동성 돌파 포지션 매도")
        positions = self.db.get_open_positions()
        for pos in positions:
            if pos.strategy == "volatility_breakout":
                self.order_manager.execute_sell(pos.ticker, "일일 리셋 매도", pos.strategy)
                time.sleep(0.5)

    def _daily_refresh(self):
        """09:05 KST - 리스크 리셋, 시장 상태 감지."""
        self.risk_manager.reset_daily()
        self._starting_balance = self.portfolio.get_total_balance()
        self.risk_manager.update_peak_balance(self._starting_balance)
        if not self.config.target_coins:
            self._refresh_coins()
        self._update_market_regime()
        logger.info(f"일일 리셋 완료 | 잔고: {format_krw(self._starting_balance)} | 시장: {self._market_regime}")

    def _update_market_regime(self):
        """BTC 기준 시장 상태 감지 후 전략 가중치 동적 조정."""
        btc_df = self.client.get_ohlcv("KRW-BTC", "day", 30)
        if btc_df is None:
            return

        self._market_regime = detect_market_regime(btc_df)

        # 시장 상태별 가중치 동적 조정
        if self._market_regime == "bull":
            # 상승장: 추세추종 + 변동성 돌파 강화
            weights = {
                "volatility_breakout": 0.35,
                "rsi_bollinger": 0.15,
                "ma_crossover": 0.25,
                "momentum_mtf": 0.25,
            }
        elif self._market_regime == "bear":
            # 하락장: RSI+볼린저(역추세) 강화, 변동성 돌파 약화
            weights = {
                "volatility_breakout": 0.10,
                "rsi_bollinger": 0.40,
                "ma_crossover": 0.30,
                "momentum_mtf": 0.20,
            }
        else:
            # 횡보장: 기본 가중치
            weights = {
                "volatility_breakout": 0.25,
                "rsi_bollinger": 0.30,
                "ma_crossover": 0.25,
                "momentum_mtf": 0.20,
            }

        self.ensemble = EnsembleStrategy(list(self.strategies.values()), weights)
        logger.info(f"시장 상태: {self._market_regime} | 가중치 조정: {weights}")

    def _daily_report(self):
        """23:00 KST - 일일 리포트 생성."""
        current_balance = self.portfolio.get_total_balance()
        pnl = current_balance - self._starting_balance
        pnl_pct = (pnl / self._starting_balance * 100) if self._starting_balance > 0 else 0

        trades_today = self.db.get_trades_today()
        trades_count = len(trades_today)

        # 승률 계산
        closed_today = [t for t in trades_today if t.side == "sell"]
        wins = 0
        for t in closed_today:
            pos = self.db.get_open_position_by_ticker(t.ticker)
            if pos and pos.pnl and pos.pnl > 0:
                wins += 1
        win_rate = (wins / len(closed_today) * 100) if closed_today else 0

        max_dd = 0.0
        if self.risk_manager.peak_balance > 0:
            max_dd = ((self.risk_manager.peak_balance - current_balance)
                      / self.risk_manager.peak_balance * 100)
            max_dd = max(max_dd, 0)

        today = now_kst().date()
        self.db.save_daily_report(
            today, self._starting_balance, current_balance,
            trades_count, win_rate, max_dd
        )

        self.notifier.send_daily_report_sync(
            str(today), self._starting_balance, current_balance,
            pnl, pnl_pct, trades_count, win_rate, max_dd
        )

        logger.info(
            f"일일 리포트 | 수익: {format_pct(pnl_pct)} | "
            f"잔고: {format_krw(current_balance)} | 거래: {trades_count}건"
        )

    def _trading_tick(self):
        """매 간격마다 실행되는 매매 로직."""
        now = now_kst()
        positions = self.db.get_open_positions()
        pos_info = ", ".join(f"{p.ticker}" for p in positions) if positions else "없음"
        krw = self.client.get_krw_balance()
        print(f"[{now.strftime('%H:%M:%S')}] 체크 | 잔고: {krw:,.0f}원 | 포지션: {pos_info}", flush=True)

        try:
            sold_any = self._check_exits()
            if sold_any:
                time.sleep(0.3)  # 거래소 상태 반영 대기
            self._check_entries()
        except Exception as e:
            logger.error(f"매매 틱 오류: {e}", exc_info=True)
            print(f"[오류] {e}")

    def _check_exits(self) -> bool:
        """단순 매도: +1% 익절, -2% 손절, 30분 시간초과."""
        positions = self.db.get_open_positions()
        if not positions:
            return False

        sold = False
        tickers = [p.ticker for p in positions]
        prices = self.client.get_current_prices(tickers)

        for pos in positions:
            current_price = prices.get(pos.ticker)
            if not current_price:
                continue

            change_pct = (current_price / pos.entry_price - 1) * 100
            self.db.update_highest_price(pos.id, current_price)

            # 1. 익절: +2.5% (수수료 0.1% 빼고 순수익 +2.4%)
            if change_pct >= 2.5:
                reason = f"익절 ({change_pct:+.2f}%)"
                logger.info(f"익절: {pos.ticker} | {reason}")
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                print(f"  [익절] {pos.ticker} | +{change_pct:.2f}%", flush=True)
                continue

            # 2. 손절: -2% (BTC/ETH/XRP는 변동성 낮으므로 넉넉하게)
            if change_pct <= -2.0:
                reason = f"손절 ({change_pct:+.2f}%)"
                logger.info(f"손절: {pos.ticker} | {reason}")
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                print(f"  [손절] {pos.ticker} | {change_pct:+.2f}%", flush=True)
                continue

            # 3. 시간초과: 30분 지나면 현재 수익률로 매도
            now_time = datetime.utcnow()
            entry_time = pos.entry_time
            if entry_time.tzinfo is not None:
                entry_time = entry_time.replace(tzinfo=None)
            elapsed = (now_time - entry_time).total_seconds() / 60

            if elapsed >= 30:
                reason = f"시간초과 ({elapsed:.0f}분, {change_pct:+.2f}%)"
                logger.info(f"시간초과: {pos.ticker} | {reason}")
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                continue

        return sold

    def _check_entries(self):
        """5분봉 기준 저점 매수. 이미 포지션 있는 코인은 스킵."""
        if not self.target_coins:
            return

        current_balance = self.client.get_krw_balance()
        can_trade, reason = self.risk_manager.can_trade(
            self.portfolio.get_total_balance()
        )
        if not can_trade:
            return

        if current_balance < 5000:
            return

        for ticker in self.target_coins:
            # 이미 이 코인 포지션 있으면 스킵
            if self.db.get_open_position_by_ticker(ticker):
                continue

            current_balance = self.client.get_krw_balance()
            if current_balance < 5000:
                break

            try:
                # 5분봉 20개 = 최근 100분 데이터
                df = self.client.get_ohlcv(ticker, "minute5", 20)
                if df is None or len(df) < 15:
                    continue

                price_now = df["close"].iloc[-1]

                # 볼린저 밴드 계산 (20봉 기준)
                closes = df["close"]
                sma20 = closes.rolling(15).mean().iloc[-1]
                std20 = closes.rolling(15).std().iloc[-1]
                bb_lower = sma20 - 2 * std20  # 하단 밴드
                bb_upper = sma20 + 2 * std20  # 상단 밴드

                # RSI 간단 계산 (14봉)
                delta = closes.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                rsi = 100 - (100 / (1 + gain / loss)) if loss > 0 else 50

                # 최근 변동 확인
                pct_5m = (price_now / df["close"].iloc[-2] - 1) if df["close"].iloc[-2] > 0 else 0
                pct_15m = (price_now / df["close"].iloc[-4] - 1) if df["close"].iloc[-4] > 0 else 0

                # ============ 매수 조건 ============
                # 볼린저 하단 근접 (저점) + RSI 낮음
                near_bb_lower = price_now <= bb_lower * 1.005  # 하단밴드 0.5% 이내
                rsi_low = rsi < 40

                # 조건1: 볼린저 하단 + RSI 낮음 = 확실한 저점
                if near_bb_lower and rsi_low:
                    reason = f"저점매수 RSI={rsi:.0f}, BB하단근접, 15분{pct_15m*100:+.1f}%"
                    logger.info(f"저점매수: {ticker} | {reason}")
                    print(f"  [저점] {ticker} | {reason}", flush=True)
                    self._execute_entry(ticker, "bb_dip", 0.8, reason)
                    continue

                # 조건2: RSI 30 이하 = 과매도 (거의 확실한 반등 지점)
                if rsi < 30:
                    reason = f"과매도 RSI={rsi:.0f}, 15분{pct_15m*100:+.1f}%"
                    logger.info(f"과매도매수: {ticker} | {reason}")
                    print(f"  [과매도] {ticker} | {reason}", flush=True)
                    self._execute_entry(ticker, "rsi_oversold", 0.85, reason)
                    continue

                # 조건3: 볼린저 하단 터치 (RSI 무관)
                if price_now <= bb_lower:
                    reason = f"BB하단터치, RSI={rsi:.0f}, 15분{pct_15m*100:+.1f}%"
                    logger.info(f"BB매수: {ticker} | {reason}")
                    print(f"  [BB하단] {ticker} | {reason}", flush=True)
                    self._execute_entry(ticker, "bb_touch", 0.7, reason)
                    continue

            except Exception as e:
                logger.debug(f"분석 오류 {ticker}: {e}")
                continue

    def _execute_entry(self, ticker: str, strategy_name: str,
                       confidence: float, reason: str):
        """매수 실행."""
        current_balance = self.client.get_krw_balance()
        stats = self.db.get_strategy_stats(strategy_name)
        amount = self.position_sizer.calculate(
            current_balance, confidence,
            stats["win_rate"], stats["avg_win"], stats["avg_loss"]
        )

        if amount >= 5000:
            result = self.order_manager.execute_buy(
                ticker, amount, strategy_name, confidence, reason
            )
            if result:
                time.sleep(0.3)
