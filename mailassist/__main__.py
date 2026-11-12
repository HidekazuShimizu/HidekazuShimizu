"""起動: python -m mailassist"""

import sys

from PySide6.QtWidgets import QApplication

from . import APP_NAME
from .db import Database
from .ui.main_window import MainWindow


def main() -> int:
    if "--edition" in sys.argv:  # ビルド確認用
        from .edition import current_edition
        print(current_edition())
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    db = Database()
    win = MainWindow(db)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
