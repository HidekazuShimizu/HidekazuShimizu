@echo off
chcp 65001 >nul
rem 自分用版（Claude Code 経由 + Claude API）をビルドする
cd /d %~dp0..
pyinstaller --noconfirm --windowed --name KyokaToriKun-Personal --icon assets\icon\icon.ico --add-data "assets\icon\icon.png;assets\icon" run.py
echo.
echo 完了: dist\KyokaToriKun-Personal\KyokaToriKun-Personal.exe
pause
