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
        self._regime_config = {
            "max_positions": self.config.risk.max_portfolio_coins,
            "position_size_mult": 1.0,
            "stop_loss_mult": 1.0,
            "take_profit_mult": 1.0,
        }

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

        # 크래시 복구: 오픈 포지션 체크
        self._recover_positions()

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

    def _recover_positions(self):
        """시작 시 오픈 포지션 체크 + 손절/익절 규칙 적용."""
        positions = self.db.get_open_positions()
        if not positions:
            print("[봇] 미결 포지션 없음")
            return

        print(f"[봇] 미결 포지션 {len(positions)}개 발견, 복구 중...")
        logger.info(f"크래시 복구: {len(positions)}개 오픈 포지션 발견")

        tickers = [p.ticker for p in positions]
        prices = self.client.get_current_prices(tickers)

        for pos in positions:
            current_price = prices.get(pos.ticker)
            if not current_price:
                logger.warning(f"복구 실패: {pos.ticker} 현재가 조회 불가")
                continue

            change_pct = (current_price / pos.entry_price - 1) * 100

            # 하드 스탑 확인
            if self.risk_manager.check_stop_loss(pos.entry_price, current_price):
                reason = f"복구 손절 {change_pct:.2f}%"
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                print(f"  [복구 손절] {pos.ticker} {change_pct:.2f}%")
                logger.info(f"복구 손절: {pos.ticker} {change_pct:.2f}%")
                time.sleep(0.5)
                continue

            # 시간 스탑 확인
            time_stop_hours = getattr(self.config.risk, 'time_stop_hours', 24)
            if pos.entry_time and change_pct < 0:
                entry_naive = pos.entry_time.replace(tzinfo=None) if pos.entry_time.tzinfo else pos.entry_time
                now_naive = datetime.utcnow()
                elapsed = (now_naive - entry_naive).total_seconds()
                if elapsed > time_stop_hours * 3600:
                    reason = f"복구 시간스탑 {elapsed/3600:.0f}h {change_pct:.2f}%"
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    print(f"  [복구 시간] {pos.ticker} {change_pct:.2f}%")
                    time.sleep(0.5)
                    continue

            # 익절 확인
            if self.risk_manager.check_take_profit(pos.entry_price, current_price):
                reason = f"복구 익절 +{change_pct:.2f}%"
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                print(f"  [복구 익절] {pos.ticker} +{change_pct:.2f}%")
                time.sleep(0.5)
                continue

            print(f"  [홀딩 유지] {pos.ticker} {change_pct:+.2f}%")
            logger.info(f"복구 홀딩: {pos.ticker} {change_pct:+.2f}%")

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
        """BTC 기준 시장 상태 감지 후 전략 가중치 + 공격성 동적 조정."""
        btc_df = self.client.get_ohlcv("KRW-BTC", "day", 30)
        if btc_df is None:
            return

        self._market_regime = detect_market_regime(btc_df)

        # 시장 상태별 전략 가중치 + 포지션/리스크 파라미터 동적 조정
        if self._market_regime == "bull":
            # 상승장: 적극 매수, 넓은 익절, 추세추종 강화
            weights = {
                "volatility_breakout": 0.35,
                "rsi_bollinger": 0.10,
                "ma_crossover": 0.30,
                "momentum_mtf": 0.25,
            }
            self._regime_config = {
                "max_positions": min(self.config.risk.max_portfolio_coins + 2, 8),
                "position_size_mult": 1.2,   # 포지션 20% 크게
                "stop_loss_mult": 1.3,       # 손절 30% 넓게 (여유)
                "take_profit_mult": 1.5,     # 익절 50% 넓게 (더 큰 수익 노림)
            }
        elif self._market_regime == "bear":
            # 하락장: 보수적, 빠른 손절, 역추세 전략 강화
            weights = {
                "volatility_breakout": 0.05,
                "rsi_bollinger": 0.45,
                "ma_crossover": 0.30,
                "momentum_mtf": 0.20,
            }
            self._regime_config = {
                "max_positions": max(self.config.risk.max_portfolio_coins - 2, 2),
                "position_size_mult": 0.7,   # 포지션 30% 작게
                "stop_loss_mult": 0.7,       # 손절 30% 좁게 (빠른 탈출)
                "take_profit_mult": 0.8,     # 익절 20% 좁게 (욕심 줄임)
            }
        else:
            # 횡보장: 스윙 트레이딩, 볼린저 밴드 강화
            weights = {
                "volatility_breakout": 0.20,
                "rsi_bollinger": 0.35,
                "ma_crossover": 0.25,
                "momentum_mtf": 0.20,
            }
            self._regime_config = {
                "max_positions": self.config.risk.max_portfolio_coins,
                "position_size_mult": 1.0,
                "stop_loss_mult": 1.0,
                "take_profit_mult": 1.0,
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

    def _get_atr_pct(self, ticker: str) -> float:
        """코인의 ATR을 현재가 대비 비율(%)로 반환. 캐시된 OHLCV 사용."""
        try:
            df = self.client.get_ohlcv(ticker, "day", 20)
            if df is None or len(df) < 14:
                return 3.0  # 기본값
            from bot.analysis.indicators import add_atr
            atr = add_atr(df, 14)
            current_price = df.iloc[-1]["close"]
            if current_price <= 0:
                return 3.0
            return (atr.iloc[-1] / current_price) * 100
        except Exception:
            return 3.0

    def _check_exits(self) -> bool:
        """매도 규칙: ATR 기반 동적 손절/익절 + 분할 매도."""
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
            peak_pct = (highest / pos.entry_price - 1) * 100
            self.db.update_highest_price(pos.id, current_price)

            # ATR 기반 동적 임계값 계산
            atr_pct = self._get_atr_pct(pos.ticker)
            # 손절: ATR × 1.5배 (변동성 큰 코인은 넓게, 작은 코인은 좁게)
            dynamic_stop = max(atr_pct * 1.5, 2.0)   # 최소 2%
            dynamic_stop = min(dynamic_stop, 8.0)     # 최대 8%
            # 익절: ATR × 2.5배
            dynamic_take = max(atr_pct * 2.5, 3.0)   # 최소 3%
            dynamic_take = min(dynamic_take, 15.0)    # 최대 15%
            # 분할 매도 라인: 익절의 60%
            partial_take = dynamic_take * 0.6

            # [1] 하드 스탑: ATR 기반 동적 손절
            if change_pct <= -dynamic_stop:
                reason = f"동적손절 {change_pct:.2f}% (ATR기반 -{dynamic_stop:.1f}%)"
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                print(f"  [손절] {pos.ticker} {change_pct:.2f}% (한도-{dynamic_stop:.1f}%)", flush=True)
                continue

            # [2] 시간 스탑: 24시간 경과 + 마이너스 → 손절
            time_stop_hours = getattr(self.config.risk, 'time_stop_hours', 24)
            if pos.entry_time and change_pct < 0:
                entry_naive = pos.entry_time.replace(tzinfo=None) if pos.entry_time.tzinfo else pos.entry_time
                elapsed = (datetime.utcnow() - entry_naive).total_seconds()
                if elapsed > time_stop_hours * 3600:
                    reason = f"시간스탑 {elapsed/3600:.0f}h {change_pct:.2f}%"
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                    print(f"  [시간] {pos.ticker} {change_pct:.2f}%", flush=True)
                    continue

            # [3] 분할 매도: 중간 익절 라인 도달 시 50% 매도
            if change_pct >= partial_take and not getattr(pos, '_partial_sold', False):
                reason = f"분할익절 +{change_pct:.2f}% (1차 {partial_take:.1f}%)"
                self.order_manager.execute_partial_sell(pos.ticker, 0.5, reason, pos.strategy)
                pos._partial_sold = True
                sold = True
                print(f"  [분할] {pos.ticker} +{change_pct:.2f}% (50% 매도)", flush=True)
                continue

            # [4] 최종 익절: ATR 기반 동적 익절
            if change_pct >= dynamic_take:
                reason = f"동적익절 +{change_pct:.2f}% (ATR기반 +{dynamic_take:.1f}%)"
                self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                sold = True
                print(f"  [익절] {pos.ticker} +{change_pct:.2f}%", flush=True)
                continue

            # [5] 어깨 매도: peak 이후 30% 되돌림 (동적 기준)
            if peak_pct >= partial_take and change_pct >= 0.5:
                drop_from_peak = peak_pct - change_pct
                if drop_from_peak >= peak_pct * 0.3:
                    reason = f"어깨매도 고점+{peak_pct:.1f}%→+{change_pct:.1f}%"
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                    print(f"  [어깨] {pos.ticker} +{change_pct:.1f}%", flush=True)
                    continue

            # [6] 트레일링 스탑: 고점 대비 ATR 1배 하락
            trailing_pct = max(atr_pct, 1.5) / 100  # 최소 1.5%
            if change_pct > 0 and highest > 0:
                drop_from_high = (highest - current_price) / highest
                if drop_from_high >= trailing_pct:
                    reason = f"트레일링 고점{peak_pct:.1f}%→{change_pct:.1f}% (ATR {atr_pct:.1f}%)"
                    self.order_manager.execute_sell(pos.ticker, reason, pos.strategy)
                    sold = True
                print(f"  [트레일] {pos.ticker} +{change_pct:.1f}%", flush=True)
                continue

        return sold

    def _check_entries(self):
        """앵상블 전략 기반 매수. 각 전략의 analyze()를 호출하고 앵상블 결과로 판단."""
        if not self.target_coins:
            return

        open_positions = self.db.get_open_positions()
        open_count = len(open_positions)
        slots = self.config.risk.max_portfolio_coins - open_count

        if slots <= 0:
            return

        current_balance = self.client.get_krw_balance()
        can_trade, reason = self.risk_manager.can_trade(
            self.portfolio.get_total_balance()
        )
        if not can_trade or current_balance < 5000:
            return

        held_tickers = {p.ticker for p in open_positions}
        buy_candidates = []

        for ticker in self.target_coins:
            if ticker in held_tickers:
                continue

            try:
                # 각 전략별 preferred_interval로 OHLCV 가져오기
                strategy_results = {}
                for name, strategy in self.strategies.items():
                    interval = strategy.get_preferred_interval()
                    candle_count = strategy.get_required_candle_count()
                    df = self.client.get_ohlcv(ticker, interval, candle_count)
                    if df is None or len(df) < candle_count // 2:
                        continue

                    current_price = self.client.get_current_price(ticker)

                    # 멀티타임프레임 전략은 여러 타임프레임 데이터 필요
                    kwargs = {"current_price": current_price}
                    if name == "momentum_mtf":
                        ohlcv_map = {}
                        for tf in strategy.timeframes:
                            tf_df = self.client.get_ohlcv(ticker, tf, 50)
                            if tf_df is not None:
                                ohlcv_map[tf] = tf_df
                        kwargs["ohlcv_by_timeframe"] = ohlcv_map

                    result = strategy.analyze(ticker, df, **kwargs)
                    strategy_results[name] = result

                if not strategy_results:
                    continue

                # 앵상블 평가
                ensemble_result = self.ensemble.evaluate(ticker, strategy_results)

                # 거래량 급등 감지: 평소 대비 3배 이상이면 신뢰도 부스트
                volume_boost = 0.0
                volume_spike = False
                try:
                    vol_df = self.client.get_ohlcv(ticker, "minute15", 30)
                    if vol_df is not None and len(vol_df) >= 20:
                        from bot.analysis.indicators import add_volume_sma
                        vol_sma = add_volume_sma(vol_df, 20)
                        curr_vol = vol_df.iloc[-1]["volume"]
                        avg_vol = vol_sma.iloc[-1]
                        if avg_vol > 0:
                            vol_ratio = curr_vol / avg_vol
                            if vol_ratio >= 3.0:
                                volume_boost = 0.15
                                volume_spike = True
                                logger.info(f"거래량 급등: {ticker} | {vol_ratio:.1f}x (부스트 +{volume_boost:.0%})")
                            elif vol_ratio >= 2.0:
                                volume_boost = 0.08
                except Exception:
                    pass

                boosted_confidence = min(ensemble_result.confidence + volume_boost, 1.0)
                spike_tag = " [VOL SPIKE]" if volume_spike else ""

                if ensemble_result.signal in (Signal.BUY, Signal.STRONG_BUY):
                    buy_candidates.append({
                        "ticker": ticker,
                        "signal": ensemble_result.signal,
                        "confidence": boosted_confidence,
                        "reason": ensemble_result.reason + spike_tag,
                        "score": ensemble_result.metadata.get("weighted_score", 0),
                    })

                # 거래량 급등이면 NEUTRAL이어도 약한 매수 후보로 포함
                elif volume_spike and ensemble_result.signal == Signal.NEUTRAL:
                    buy_candidates.append({
                        "ticker": ticker,
                        "signal": Signal.BUY,
                        "confidence": volume_boost,
                        "reason": f"거래량 급등 매수 (신호 NEUTRAL이나 거래량 3x+){spike_tag}",
                        "score": 0,
                    })

            except Exception as e:
                logger.debug(f"앙상블 분석 오류 {ticker}: {e}")
                continue

        # 신뢰도 높은 순 정렬
        buy_candidates.sort(key=lambda x: x["confidence"], reverse=True)

        bought = 0
        for candidate in buy_candidates:
            if bought >= slots:
                break

            current_balance = self.client.get_krw_balance()
            if current_balance < 5000:
                break

            ticker = candidate["ticker"]
            confidence = candidate["confidence"]
            signal_name = candidate["signal"].name
            reason = f"앙상블 {signal_name} | {candidate['reason']}"

            logger.info(f"앙상블 매수: {ticker} | {reason} | conf={confidence:.2f}")
            print(f"  [매수 {open_count+bought+1}/{self.config.risk.max_portfolio_coins}] {ticker} | {reason}", flush=True)
            self._execute_entry(ticker, "ensemble", confidence, reason)
            bought += 1

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
