# PyInstaller spec for BryMaps (run from repo root: pyinstaller tools/brymaps.spec)
# Paths resolve relative to this spec's location so it works from any CWD / on CI.
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))  # noqa: F821 (SPECPATH injected)

datas = [
    (os.path.join(ROOT, 'brymaps', 'qml'), 'qml'),
    (os.path.join(ROOT, 'engine'), 'engine'),
    (os.path.join(ROOT, 'data'), 'data'),
]
binaries = []
# engine/*.py are bundled as data (loaded via sys.path at runtime), so PyInstaller does not
# see their imports — declare the non-obvious ones the engine needs here.
hiddenimports = ['mapbox_vector_tile', 'sqlite3', 'gzip', 'zlib']
for pkg in ('mapbox_vector_tile',):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, 'brymaps', 'main.py')],
    pathex=[os.path.join(ROOT, 'brymaps')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BryMaps',
          console=False, icon=os.path.join(ROOT, 'data', 'icon.png'))
coll = COLLECT(exe, a.binaries, a.datas, name='BryMaps')
