"""Build assets/app.ico (all Windows sizes) from assets/app_icon_source.jpg.

Run once after changing the source picture:  python tools/make_icon.py
The white area around the rounded tile becomes transparent.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "app_icon_source.jpg"
ICON = ROOT / "assets" / "app.ico"
ICON_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
WHITE_TOLERANCE = 40  # JPEG noise: "almost white" counts as background
MARKER = (255, 0, 255)


def remove_outer_white(image: Image.Image) -> Image.Image:
    """Flood-fill the white border from each corner and make it transparent."""
    rgb = image.convert("RGB")
    for corner in [(0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1)]:
        ImageDraw.floodfill(rgb, corner, MARKER, thresh=WHITE_TOLERANCE)
    difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, MARKER)).convert("L")
    alpha = difference.point(lambda value: 0 if value == 0 else 255)
    result = image.convert("RGBA")
    result.putalpha(alpha)
    return result.crop(result.getbbox())


def main() -> None:
    icon = remove_outer_white(Image.open(SOURCE))
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    square.save(ICON, sizes=ICON_SIZES)
    print(f"Wrote {ICON}")


if __name__ == "__main__":
    main()
