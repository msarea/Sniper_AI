# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all  # <--- Add this line at the very top

# Trigger a total collection of the dns library
tmp_ret = collect_all('dns')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=tmp_ret[1],    # <--- Add tmp_ret[1]
    datas=tmp_ret[0] + [('templates', 'templates'), ('static', 'static')], # <--- Add tmp_ret[0]
    hiddenimports=tmp_ret[2] + [
        'eventlet.hubs.epolls', 
        'eventlet.hubs.kqueue', 
        'eventlet.hubs.selects',
        'engineio.async_drivers.eventlet', 
        'flask_socketio.async_eventlet',
        'dns.rdtypes.ANY',
        'dns.rdtypes.IN',
        'dns.rdtypes.CH'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Sniper_AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['sniper.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sniper_AI',
)
app = BUNDLE(
    coll,
    name='Sniper_AI.app',
    icon='sniper.icns',
    bundle_identifier=None,
)
