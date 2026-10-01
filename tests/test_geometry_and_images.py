from datetime import datetime

import pytest
from PIL import Image

from ocr_capture.geometry import Point, ScreenRect
from ocr_capture.image_output import build_file_name, flatten_alpha, mask_outside_polygon, save_image


def test_rect_from_corners_any_direction():
    assert ScreenRect.from_corners(Point(10, 20), Point(5, 2)) == ScreenRect(5, 2, 6, 19)


def test_rect_bounding_with_negative_coordinates():
    rect = ScreenRect.bounding([Point(-1920, 5), Point(-10, 300), Point(-500, -40)])
    assert rect == ScreenRect(-1920, -40, 1911, 341)
    assert rect.right == -9


def test_rect_dict_validation():
    assert ScreenRect.from_dict(ScreenRect(1, 2, 3, 4).to_dict()) == ScreenRect(1, 2, 3, 4)
    for bad in ({"left": 1}, {"left": 0, "top": 0, "width": 0, "height": 5}, {"left": 0.5, "top": 0, "width": 1, "height": 1}):
        with pytest.raises(ValueError):
            ScreenRect.from_dict(bad)


def test_polygon_mask_makes_outside_transparent():
    image = Image.new("RGB", (10, 10), "red")
    triangle = [Point(100, 100), Point(109, 100), Point(100, 109)]
    masked = mask_outside_polygon(image, triangle, origin=Point(100, 100))
    assert masked.mode == "RGBA"
    assert masked.getpixel((1, 1))[3] == 255
    assert masked.getpixel((9, 9))[3] == 0


def test_flatten_alpha_uses_background():
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    assert flatten_alpha(image, "#00FF00").getpixel((0, 0)) == (0, 255, 0)


def test_file_name_format():
    assert build_file_name("image", "PNG", datetime(2026, 1, 2, 3, 4, 5, 6)) == "image_20260102_030405_000006.png"


@pytest.mark.parametrize("file_format", ["png", "jpg", "bmp"])
def test_save_image_all_formats(tmp_path, file_format):
    path = save_image(Image.new("RGBA", (4, 4), (1, 2, 3, 0)), tmp_path / "out", "x", file_format, "#FFFFFF")
    assert path.exists()
    assert path.suffix == f".{file_format}"
