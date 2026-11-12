"""エディション（自分用版 / 販売版）の判定。

販売版のビルドでは `mailassist.ai.cli_backend` モジュールをパッケージから
除外する（build/build_commercial.bat 参照）。モジュールが存在しなければ
販売版として動作し、Claude Code 経由の接続は選択肢にも表示されない。

開発中に販売版の動作を確認したいときは、環境変数
MAILASSIST_EDITION=commercial を設定して起動する。
"""

import importlib.util
import os

PERSONAL = "personal"
COMMERCIAL = "commercial"


def current_edition() -> str:
    forced = os.environ.get("MAILASSIST_EDITION", "").strip().lower()
    if forced in (PERSONAL, COMMERCIAL):
        return forced
    try:
        found = importlib.util.find_spec("mailassist.ai.cli_backend") is not None
    except (ImportError, ValueError):
        found = False
    return PERSONAL if found else COMMERCIAL


def is_personal() -> bool:
    return current_edition() == PERSONAL
