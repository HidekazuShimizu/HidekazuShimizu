@echo off
chcp 65001 >nul
rem 販売版（Claude API のみ）をビルドする。Claude Code 接続のコードは含めない。
cd /d %~dp0..
pyinstaller --noconfirm --windowed --name MailAssist --exclude-module mailassist.ai.cli_backend run.py
echo.
echo 完了: dist\MailAssist\MailAssist.exe
pause
