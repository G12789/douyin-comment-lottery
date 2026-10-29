@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在安装依赖...
python -m pip install -r requirements.txt -q
echo 正在安装 Playwright 浏览器（首次较慢）...
python -m playwright install chromium
echo.
echo 启动自动抽奖...
python auto_lottery.py
pause
