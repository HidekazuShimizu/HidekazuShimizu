"""PyInstaller 用の起動スクリプト。"""
import sys

from mailassist.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
