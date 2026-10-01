import json

from ocr_capture.config import DEFAULT_HOTKEYS, HotkeyAction
from ocr_capture.geometry import ScreenRect
from ocr_capture.settings import AppSettings, SettingsStore, settings_from_dict


def test_missing_file_gives_defaults(tmp_path):
    settings, warnings = SettingsStore(tmp_path / "settings.json").load()
    assert settings == AppSettings()
    assert warnings == []


def test_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    original = AppSettings(region=ScreenRect(-100, 20, 300, 40)).with_hotkey(HotkeyAction.SET_REGION, "Ctrl+Alt+R")
    store.save(original)
    loaded, warnings = store.load()
    assert loaded == original
    assert warnings == []


def test_hotkeys_are_at_top_of_file(tmp_path):
    path = tmp_path / "settings.json"
    SettingsStore(path).save(AppSettings())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[1].strip() == '"hotkeys": {'
    assert lines[2].strip() == f'"set_region": "{DEFAULT_HOTKEYS[HotkeyAction.SET_REGION]}",'


def test_bad_values_fall_back_per_field():
    data = {
        "hotkeys": {"set_region": "nonsense+key", "capture_image": "ctrl+shift+i", "bogus": "Alt+B"},
        "region": {"left": 1},
        "ocr": {"upscale_factor": "big", "language": "de-DE"},
        "text_capture": {"similarity_threshold": 5.0},
        "unknown_section": {},
    }
    settings, warnings = settings_from_dict(data)
    assert settings.hotkeys["set_region"] == DEFAULT_HOTKEYS[HotkeyAction.SET_REGION]
    assert settings.hotkeys["capture_image"] == "Ctrl+Shift+I"
    assert "bogus" not in settings.hotkeys
    assert settings.region is None
    assert settings.ocr.language == "de-DE"
    assert settings.ocr.upscale_factor == AppSettings().ocr.upscale_factor
    assert settings.text_capture == AppSettings().text_capture
    assert len(warnings) == 6


def test_bool_is_not_accepted_as_number():
    settings, warnings = settings_from_dict({"text_capture": {"live_caption_interval_ms": True}})
    assert settings.text_capture.live_caption_interval_ms == 0
    assert warnings


def test_int_is_accepted_for_float():
    settings, _ = settings_from_dict({"ocr": {"upscale_factor": 3}})
    assert settings.ocr.upscale_factor == 3.0
    assert isinstance(settings.ocr.upscale_factor, float)


def test_broken_json_is_backed_up(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    settings, warnings = SettingsStore(path).load()
    assert settings == AppSettings()
    assert "not valid JSON" in warnings[0]
    assert not path.exists()
    assert len(list(tmp_path.glob("settings.json.broken-*"))) == 1


def test_save_is_valid_json_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "settings.json"
    SettingsStore(path).save(AppSettings())
    json.loads(path.read_text(encoding="utf-8"))
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
