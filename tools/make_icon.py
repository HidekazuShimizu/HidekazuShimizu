"""シンボルマーク画像からアプリ用アイコン一式を作る。

元画像: assets/icon/source/symbol_original.webp（白背景・影付きの角丸タイル）

出力（assets/icon/）:
  icon.png       256px  タイル版（ウィンドウのアイコン）
  icon_512.png   512px  タイル版
  mark.png       512px  マークのみ・背景透明（Web・資料用）
  icon.ico       16〜256px（48px以上はタイル版、32px以下は小さくても見やすいマークのみ版）

使い方: python tools/make_icon.py
元画像を差し替えた場合は、TILE_BOX（タイルの外枠の位置）を合わせて調整する。
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icon"
SOURCE = ICON_DIR / "source" / "symbol_original.webp"

TILE_BOX = (90, 100, 1163, 1160)  # 元画像内のタイルの左・上・右・下
TILE_RADIUS = 250                  # タイルの角の丸み（元画像のピクセル単位）
INSET = 5                          # 縁の影を切り落とす幅
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
SMALL_MAX = 32                     # この大きさ以下はマークのみ版を使う


def tile_mask(w: int, h: int) -> Image.Image:
    k = 4  # 縁をなめらかにするため拡大して描いてから縮小
    m = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (INSET * k, INSET * k, (w - INSET) * k, (h - INSET) * k),
        radius=TILE_RADIUS * k, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def to_square(im: Image.Image, margin: float = 0.0) -> Image.Image:
    w, h = im.size
    side = int(max(w, h) * (1 + margin))
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - w) // 2, (side - h) // 2), im)
    return sq


def make_tile(src: Image.Image) -> tuple[Image.Image, Image.Image]:
    tile = src.crop(TILE_BOX)
    mask = tile_mask(*tile.size)
    rgba = tile.convert("RGBA")
    rgba.putalpha(mask)
    return to_square(rgba), mask


def make_mark(src: Image.Image, mask: Image.Image) -> Image.Image:
    """タイルの白地を透明にし、マーク部分だけを取り出す。"""
    tile = src.crop(TILE_BOX)
    work = tile.copy()
    ImageDraw.floodfill(work, (60, 300), (255, 0, 255), thresh=40)  # タイルの白地を塗りつぶして判定
    bg = np.all(np.array(work) == [255, 0, 255], axis=-1)
    edge = np.array(Image.fromarray((bg * 255).astype("uint8")).filter(ImageFilter.MaxFilter(7))) > 0
    orig = np.array(tile).astype(float)

    alpha = np.ones(bg.shape)
    alpha[bg] = 0
    # 境界のにじみ（白との中間色）を半透明に変換して白いふちを防ぐ
    zone = edge & ~bg
    a = np.clip((255 - orig[zone]).max(axis=1) / 255.0 * 1.15, 0, 1)
    alpha[zone] = a
    rgb = orig.copy()
    safe = np.maximum(a, 1e-3)[:, None]
    rgb[zone] = np.clip((orig[zone] - (1 - safe) * 255) / safe, 0, 255)
    inner = np.array(mask.filter(ImageFilter.MinFilter(15))) / 255.0
    alpha = alpha * (inner > 0.99)

    mark = Image.fromarray(np.dstack([rgb, alpha * 255]).astype("uint8"), "RGBA")
    bbox = mark.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return to_square(mark.crop(bbox), margin=0.04)


def main() -> None:
    src = Image.open(SOURCE).convert("RGB")
    tile, mask = make_tile(src)
    mark = make_mark(src, mask)

    def sized(im, s):
        return im.resize((s, s), Image.LANCZOS)

    sized(tile, 256).save(ICON_DIR / "icon.png")
    sized(tile, 512).save(ICON_DIR / "icon_512.png")
    sized(mark, 512).save(ICON_DIR / "mark.png")

    frames = [sized(mark if s <= SMALL_MAX else tile, s) for s in ICO_SIZES]
    frames[-1].save(ICON_DIR / "icon.ico", format="ICO",
                    sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])
    print("generated:", ", ".join(p.name for p in sorted(ICON_DIR.glob("*.*"))))


if __name__ == "__main__":
    main()
