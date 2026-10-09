from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parent
icon_path = project_root / "packaging" / "assets" / "wordwright.ico"
datas = [
    (
        str(project_root / "src" / "wordwright" / "assets"),
        "wordwright/assets",
    )
]
binaries = []
hiddenimports = []

for package in (
    "av",
    "ctranslate2",
    "faster_whisper",
    "onnxruntime",
    "pynput",
    "pystray",
    "sounddevice",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Wordwright",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(icon_path),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Wordwright",
)

