@echo off
chcp 65001 >nul
rem 初回セットアップ（Python 3.11 以上が必要）
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
echo.
echo セットアップ完了。start.bat で起動できます。
pause
