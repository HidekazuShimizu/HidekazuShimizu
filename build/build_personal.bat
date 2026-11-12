@echo off
chcp 65001 >nul
rem 自分用版（Claude Code 経由 + Claude API）をビルドする
cd /d %~dp0..
pyinstaller --noconfirm --windowed --name MailAssist-Personal run.py
echo.
echo 完了: dist\MailAssist-Personal\MailAssist-Personal.exe
pause
