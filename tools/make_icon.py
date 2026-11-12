"""assets/icon/icon.svg から PNG と Windows 用 .ico を作る。

使い方: python tools/make_icon.py
（SVG内の「可」の文字は日本語フォントで描画されるため、生成済みの PNG/ICO をリポジトリに含めている）
"""
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icon"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(renderer: QSvgRenderer, size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> int:
    QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(ICON_DIR / "icon.svg"))
    images = {s: render(renderer, s) for s in SIZES}
    images[256].save(ICON_DIR / "icon.png")
    render(renderer, 512).save(ICON_DIR / "icon_512.png")
    images[256].save(ICON_DIR / "icon.ico", sizes=[(s, s) for s in SIZES],
                     append_images=[images[s] for s in SIZES if s != 256])
    print("generated:", ", ".join(p.name for p in sorted(ICON_DIR.glob("icon*"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
