# -*- mode: python ; coding: utf-8 -*-
# PDFree PyInstaller spec file
# Build with: pyinstaller PDFree.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('LOGO.svg', '.'),
    ],
    hiddenimports=[
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',
        'pdfminer.layout',
        'pdfminer.converter',
        'pdfminer.pdfpage',
        'pypdf',
        'fitz',
        'PIL._tkinter_finder',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDFree',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # compress the binary (install UPX for smaller size)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # no terminal window — GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='LOGO.ico',
)
