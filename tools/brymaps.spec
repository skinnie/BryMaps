# PyInstaller spec for BryMaps (run from repo root: pyinstaller tools/brymaps.spec)
from PyInstaller.utils.hooks import collect_all
import os

datas = [('brymaps/qml', 'qml'), ('engine', 'engine'), ('data', 'data')]
binaries = []
hiddenimports = ['mapbox_vector_tile']
for pkg in ('mapbox_vector_tile',):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(['brymaps/main.py'], pathex=['brymaps'], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='BryMaps',
          console=False, icon=os.path.join('data', 'icon.png'))
coll = COLLECT(exe, a.binaries, a.datas, name='BryMaps')
