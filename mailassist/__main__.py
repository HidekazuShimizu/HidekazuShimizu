"""起動: python -m mailassist"""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME
from .db import Database
from .resources import icon_path
from .ui.main_window import MainWindow


def main() -> int:
    if "--edition" in sys.argv:  # ビルド確認用
        from .edition import current_edition
        print(current_edition())
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(icon_path())))
    if sys.platform == "win32":
        # タスクバーに Python ではなくこのアプリのアイコンを表示させる
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KyokaToriKun.App")
    db = Database()
    win = MainWindow(db)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
