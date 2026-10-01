# PyInstaller recipe: builds dist\OcrRegionCapture.exe (one file, no console).
# Run through build_exe.ps1, or: pyinstaller --noconfirm OcrRegionCapture.spec
from PyInstaller.utils.hooks import collect_submodules

EXE_NAME = "OcrRegionCapture"

# The WinRT projection loads its namespaces dynamically; list them explicitly.
hidden_imports = collect_submodules("winrt")

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    hiddenimports=hidden_imports,
    excludes=["tkinter", "pytest", "unittest", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name=EXE_NAME,
    console=False,
    upx=False,
)
