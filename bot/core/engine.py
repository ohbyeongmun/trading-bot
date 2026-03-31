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

        # 코인 선정
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
        """09:05 KST - 코인 재선정, 리스크 리셋, 시장 상태 감지."""
        self.risk_manager.reset_daily()
        self._starting_balance = self.portfolio.get_total_balance()
        self.risk_manager.update_peak_balance(self._starting_balance)
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
        """오픈 포지션 퇴장 조건 - 트레일링으로 수익 극대화, 손절은 넓게."""
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
            highest = max(pos.highest_price or pos.entry_price, current_price)

            # 최고가 업데이트 (매도 판단 전에 반드시)
            self.db.update_highest_price(pos.id, current_price)

            # ========================================
            # 1. 손절: -1.5% (잡음에 안 걸리는 넓은 손절)
            # ========================================
            if change_pct <= -1.5:
                reason = f"손절 ({change_pct:+.2f}%)"
                logger.info(f"손절: {pos.ticker} | {reason}")
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                continue

            # ========================================
            # 2. 수익 구간 트레일링 (핵심: 수익은 끝까지 먹는다)
            # ========================================
            if highest > pos.entry_price:
                peak_profit_pct = (highest / pos.entry_price - 1) * 100
                drop_from_peak_pct = (highest - current_price) / highest * 100

                # 수익 +3% 이상 찍었으면: 고점 대비 -0.7% 빠지면 매도 (타이트 트레일링)
                if peak_profit_pct >= 3.0 and drop_from_peak_pct >= 0.7:
                    reason = f"트레일링 익절 (고점+{peak_profit_pct:.1f}%, 현재+{change_pct:.1f}%)"
                    logger.info(f"트레일링 익절: {pos.ticker} | {reason}")
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                    continue

                # 수익 +1% 이상 찍었으면: 고점 대비 -1% 빠지면 매도
                if peak_profit_pct >= 1.0 and drop_from_peak_pct >= 1.0:
                    reason = f"트레일링 매도 (고점+{peak_profit_pct:.1f}%, 현재+{change_pct:.1f}%)"
                    logger.info(f"트레일링: {pos.ticker} | {reason}")
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                    continue

                # 수익 +0.5% 이상인데 원금 아래로 내려가면: 본전 매도
                if peak_profit_pct >= 0.5 and change_pct <= 0.0:
                    reason = f"본전 청산 (고점+{peak_profit_pct:.1f}%→현재{change_pct:+.1f}%)"
                    logger.info(f"본전 청산: {pos.ticker} | {reason}")
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                    continue

            # ========================================
            # 3. 시간 초과: 15분 지났는데 수익 없으면 정리
            # ========================================
            now_time = datetime.utcnow()
            entry_time = pos.entry_time
            if entry_time.tzinfo is not None:
                entry_time = entry_time.replace(tzinfo=None)
            elapsed = (now_time - entry_time).total_seconds() / 60

            if elapsed >= 15 and change_pct < 0.5:
                reason = f"시간초과 ({elapsed:.0f}분, {change_pct:+.2f}%)"
                logger.info(f"시간초과: {pos.ticker} | {reason}")
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                continue

        return sold

    def _check_entries(self):
        """거래량+급등 감지 → 즉시 공격 매수. 조건 최소화, 최대한 많이."""
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

        # 1분봉 스캔 - 모든 타겟 코인
        candidates = []
        for ticker in self.target_coins:
            try:
                df = self.client.get_ohlcv(ticker, "minute1", 15)
                if df is None or len(df) < 6:
                    continue

                price_now = df["close"].iloc[-1]
                price_1m = df["close"].iloc[-2]
                price_3m = df["close"].iloc[-4]
                price_5m = df["close"].iloc[-6]

                vol_now = df["volume"].iloc[-1]
                vol_avg = df["volume"].iloc[-11:-1].mean() if len(df) >= 11 else df["volume"].iloc[:-1].mean()
                vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0

                pct_1m = (price_now / price_1m - 1) if price_1m > 0 else 0
                pct_3m = (price_now / price_3m - 1) if price_3m > 0 else 0
                pct_5m = (price_now / price_5m - 1) if price_5m > 0 else 0

                # 종합 점수 = 거래량 비율 + 가격 상승률
                score = vol_ratio * 0.5 + pct_1m * 300 + pct_3m * 200 + pct_5m * 100

                candidates.append({
                    "ticker": ticker,
                    "price": price_now,
                    "pct_1m": pct_1m,
                    "pct_3m": pct_3m,
                    "pct_5m": pct_5m,
                    "vol_ratio": vol_ratio,
                    "score": score,
                })
            except Exception as e:
                logger.debug(f"스캔 오류 {ticker}: {e}")
                continue

        if not candidates:
            return

        # 점수 높은 순 정렬
        candidates.sort(key=lambda x: x["score"], reverse=True)

        bought_count = 0
        for coin in candidates:
            if bought_count >= 5:  # 한 틱에 최대 5개
                break

            current_balance = self.client.get_krw_balance()
            if current_balance < 5000:
                break

            can_trade, _ = self.risk_manager.can_trade(
                self.portfolio.get_total_balance()
            )
            if not can_trade:
                break

            ticker = coin["ticker"]
            vol_ratio = coin["vol_ratio"]
            pct_1m = coin["pct_1m"]
            pct_3m = coin["pct_3m"]
            pct_5m = coin["pct_5m"]

            # ---- 매수 조건: 아래 중 하나만 충족하면 매수 ----

            # 거래량 폭발 (1.5배 이상 + 가격 양수)
            if vol_ratio >= 1.5 and pct_1m > 0:
                confidence = min(0.9, 0.4 + vol_ratio * 0.06)
                reason = f"거래량급증 vol x{vol_ratio:.1f}, 1분{pct_1m*100:+.2f}%"
                self._execute_entry(ticker, "volume_surge", confidence, reason)
                bought_count += 1
                continue

            # 가격 급등 (1분에 0.15% 이상 상승)
            if pct_1m >= 0.0015 and pct_3m > 0:
                confidence = min(0.8, 0.3 + pct_1m * 30)
                reason = f"급등감지 1분{pct_1m*100:+.2f}%, 3분{pct_3m*100:+.2f}%"
                self._execute_entry(ticker, "momentum_surge", confidence, reason)
                bought_count += 1
                continue

            # 연속 상승 (1분, 3분, 5분 모두 양수)
            if pct_1m > 0 and pct_3m > 0 and pct_5m > 0 and pct_5m >= 0.002:
                confidence = min(0.7, 0.3 + pct_5m * 15)
                reason = f"연속상승 5분{pct_5m*100:+.2f}%, vol x{vol_ratio:.1f}"
                self._execute_entry(ticker, "trend_ride", confidence, reason)
                bought_count += 1
                continue

        if bought_count > 0:
            print(f"  >>> {bought_count}개 코인 매수 완료!", flush=True)

    def _execute_entry(self, ticker: str, strategy_name: str,
                       confidence: float, reason: str):
        """매수 실행 헬퍼."""
        current_balance = self.client.get_krw_balance()
        stats = self.db.get_strategy_stats(strategy_name)
        amount = self.position_sizer.calculate(
            current_balance, confidence,
            stats["win_rate"], stats["avg_win"], stats["avg_loss"]
        )

        if amount >= 5000:
            logger.info(f"매수: {ticker} | {reason} | 신뢰도: {confidence:.2f} | 금액: {format_krw(amount)}")
            print(f"  [매수] {ticker} | {reason}", flush=True)
            result = self.order_manager.execute_buy(
                ticker, amount, strategy_name, confidence, reason
            )
            if result:
                time.sleep(0.2)
