@echo off
set PATH=C:\Users\User\AppData\Local\Programs\Python\Python314;C:\Users\User\AppData\Local\Programs\Python\Python314\Scripts;%PATH%
echo [백테스트 실행]
python scripts/backtest_runner.py %*
pause
