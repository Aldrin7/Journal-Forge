#!/usr/bin/env python3
"""
PaperForge — PyInstaller Build Configuration
Generates standalone executable without C compilation (RAM-safe).
"""
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def generate_spec():
    """Generate PyInstaller .spec file."""
    spec = f'''# -*- mode: python ; coding: utf-8 -*-
# PaperForge — PyInstaller Spec

a = Analysis(
    ['{PROJECT_ROOT}/pipeline/translator.py'],
    pathex=['{PROJECT_ROOT}'],
    binaries=[],
    datas=[
        ('{PROJECT_ROOT}/filters', 'filters'),
        ('{PROJECT_ROOT}/templates', 'templates'),
        ('{PROJECT_ROOT}/data', 'data'),
    ],
    hiddenimports=[
        'docx',
        'lxml',
        'yaml',
        'citeproc',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PaperForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PaperForge',
)
'''
    spec_path = PROJECT_ROOT / "build" / "PaperForge.spec"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(spec)
    print(f"Spec file written to: {spec_path}")
    return spec_path


def build():
    """Run PyInstaller build."""
    import subprocess
    spec_path = generate_spec()
    result = subprocess.run(
        ["pyinstaller", "--clean", str(spec_path)],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode == 0:
        print(f"\n✅ Build complete: {PROJECT_ROOT / 'dist' / 'PaperForge'}")
    else:
        print(f"\n❌ Build failed")
    return result.returncode


if __name__ == "__main__":
    if "--spec-only" in sys.argv:
        generate_spec()
    else:
        sys.exit(build())
