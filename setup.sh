#!/bin/bash
# Trading Bot v2 초기 셋업
# 풀 받은 후 한 번만 실행

echo "=== Trading Bot v2 Setup ==="

# 1. Python 의존성
echo "[1/4] Python 패키지 설치..."
pip install -r requirements.txt 2>/dev/null
pip install fastapi uvicorn 2>/dev/null

# 2. config.yaml 생성
if [ ! -f config.yaml ]; then
    echo "[2/4] config.yaml 생성..."
    cp config.example.yaml config.yaml
    echo "  ⚠ config.yaml에 Upbit API 키를 입력하세요!"
else
    echo "[2/4] config.yaml 이미 존재"
fi

# 3. 대시보드 의존성
echo "[3/4] 대시보드 패키지 설치..."
cd dashboard
npm install
if [ ! -f .env.local ]; then
    cp .env.example .env.local
    echo "  .env.local 생성 완료"
else
    echo "  .env.local 이미 존재"
fi
cd ..

# 4. 데이터 디렉토리
echo "[4/4] 데이터 디렉토리 생성..."
mkdir -p data/logs data/backup

echo ""
echo "=== 셋업 완료! ==="
echo ""
echo "실행 방법:"
echo "  1. config.yaml에 Upbit API 키 입력"
echo "  2. python -m api.main        (API 서버 + 봇)"
echo "  3. cd dashboard && npm run dev (대시보드)"
echo "  4. http://localhost:3000 접속"
