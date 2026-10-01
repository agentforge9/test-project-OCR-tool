"""All colours and the Qt style sheet. Change the look here only."""

from __future__ import annotations

ACCENT = "#3F51B5"
ACCENT_DARK = "#303F9F"
TEAL = "#00A88F"
START_COLOR = "#2E7D32"
START_HOVER = "#1B5E20"
STOP_COLOR = "#C62828"
STOP_HOVER = "#8E0000"
WINDOW_BG = "#F4F6FB"
CARD_BG = "#FFFFFF"
BORDER = "#DDE2EE"
TEXT = "#1F2433"
MUTED_TEXT = "#6B7280"
STATUS_OK_BG = "#E8F5E9"
STATUS_OK_TEXT = "#1B5E20"
STATUS_ERROR_BG = "#FDECEA"
STATUS_ERROR_TEXT = "#B71C1C"

HEADER_ICON_SIZE_PX = 44
CARD_RADIUS_PX = 10
INPUT_RADIUS_PX = 6
BUTTON_RADIUS_PX = 8

STYLE_SHEET = f"""
QWidget#MainWindow {{ background: {WINDOW_BG}; color: {TEXT}; font-size: 10pt; }}
QLabel#Title {{ font-size: 15pt; font-weight: 600; color: {ACCENT_DARK}; }}
QLabel#Subtitle {{ color: {MUTED_TEXT}; }}
QLabel#Hint, QLabel#Region {{ color: {MUTED_TEXT}; }}
QGroupBox {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: {CARD_RADIUS_PX}px;
    margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {ACCENT_DARK}; }}
QGroupBox QLabel {{ font-weight: normal; }}
QLineEdit {{
    background: {WINDOW_BG}; border: 1px solid {BORDER}; border-radius: {INPUT_RADIUS_PX}px;
    padding: 5px 8px; font-family: Consolas, monospace; font-weight: normal;
}}
QLineEdit:focus {{ border: 2px solid {ACCENT}; background: {CARD_BG}; }}
QLineEdit:disabled {{ color: {MUTED_TEXT}; }}
QPushButton {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: {BUTTON_RADIUS_PX}px;
    padding: 6px 12px; font-weight: normal;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED_TEXT}; }}
QPushButton#StartButton[running="false"] {{
    background: {START_COLOR}; color: white; border: none; font-size: 12pt; font-weight: 600;
}}
QPushButton#StartButton[running="false"]:hover {{ background: {START_HOVER}; }}
QPushButton#StartButton[running="true"] {{
    background: {STOP_COLOR}; color: white; border: none; font-size: 12pt; font-weight: 600;
}}
QPushButton#StartButton[running="true"]:hover {{ background: {STOP_HOVER}; }}
QLabel#Status {{ border-radius: {INPUT_RADIUS_PX}px; padding: 6px 10px; }}
QLabel#Status[error="false"] {{ background: {STATUS_OK_BG}; color: {STATUS_OK_TEXT}; }}
QLabel#Status[error="true"] {{ background: {STATUS_ERROR_BG}; color: {STATUS_ERROR_TEXT}; }}
QListWidget {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: {INPUT_RADIUS_PX}px;
    font-weight: normal;
}}
QListWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {WINDOW_BG}; }}
QListWidget::item:selected {{ background: {ACCENT}; color: white; }}
"""
