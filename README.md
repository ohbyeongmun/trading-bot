# Upbit 코인 트레이딩봇

Upbit 현물 거래 자동화 봇. 4가지 전략을 앙상블로 결합하여 수익을 극대화합니다.

## 전략
1. **변동성 돌파** (35%) - 래리 윌리엄스 전략, 한국 시장 검증 완료
2. **RSI + 볼린저 밴드** (25%) - 평균회귀, 횡보장 수익
3. **이동평균 크로스오버** (20%) - 추세 추종, 거래량 확인
4. **멀티타임프레임 모멘텀** (20%) - 다중 시간대 정렬

## 리스크 관리
- 손절 3% / 익절 5% / 트레일링 스탑 2%
- 일일 손실 한도 3%, 최대 낙폭 10%
- Half-Kelly 포지션 사이징

## 설치

```bash
pip install -r requirements.txt
```

## 설정

```bash
cp config.example.yaml config.yaml
```

`config.yaml`에 Upbit API 키와 텔레그램 봇 토큰을 입력하세요.

### Upbit API 키 발급
1. https://upbit.com/mypage/open_api_management 접속
2. 자산조회, 주문조회, 주문하기 권한 체크
3. 허용 IP 설정 (보안 필수)

### 텔레그램 봇 설정 (선택)
1. @BotFather에서 봇 생성 → 토큰 획득
2. 봇에 메시지 전송 후 chat_id 확인

## 실행

```bash
# 실전 매매
python main.py

# 모의 실행 (dry_run: true 설정)
python main.py

# 백테스트
python scripts/backtest_runner.py
python scripts/backtest_runner.py --ticker KRW-BTC --days 180
python scripts/backtest_runner.py --top 10 --capital 2000000
```

## 운영 사이클 (KST)
- **08:55** - 변동성 돌파 포지션 전량 매도
- **09:05** - 코인 재선정, 목표가 계산
- **09:10~** - 10초 간격 모니터링 (진입/퇴장)
- **23:00** - 일일 리포트 텔레그램 발송

## 주의사항
- 투자 손실의 책임은 사용자에게 있습니다
- 반드시 `dry_run: true`로 먼저 테스트하세요
- 소액으로 충분히 테스트 후 투자금을 늘리세요
- API 키에 허용 IP를 반드시 설정하세요
