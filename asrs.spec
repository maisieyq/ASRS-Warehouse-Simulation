# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


streamlit_datas, streamlit_binaries, streamlit_hiddenimports = (
    collect_all("streamlit")
)

matplotlib_datas, matplotlib_binaries, matplotlib_hiddenimports = (
    collect_all("matplotlib")
)


datas = []

datas += streamlit_datas
datas += matplotlib_datas

datas += [
    ("app.py", "."),
    ("common.css", "."),
    ("customConfig.css", "."),
    ("predefinedScenario.css", "."),
]


binaries = []

binaries += streamlit_binaries
binaries += matplotlib_binaries


hiddenimports = []

hiddenimports += streamlit_hiddenimports
hiddenimports += matplotlib_hiddenimports

hiddenimports += [
    "dashboard_common",
    "customConfig",
    "predefinedScenario",

    "ScenarioBasicConfig",
    "ScenarioBasicConfig.scenarios",
    "ScenarioBasicConfig.simulation",
    "ScenarioBasicConfig.animation",
    "ScenarioBasicConfig.graph",

    "simpy",
    "pandas",
    "numpy",
    "PIL",
]


a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)


pyz = PYZ(
    a.pure,
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ASRS_Warehouse_Simulation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)