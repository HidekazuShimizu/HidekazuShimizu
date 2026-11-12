"""アイコンなどの同梱ファイルの場所（ソース実行時と exe 実行時の両方に対応）。"""

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def icon_path() -> Path:
    return resource_path("assets/icon/icon.png")
