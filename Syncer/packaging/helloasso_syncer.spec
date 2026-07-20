# PyInstaller spec file for HelloAsso Syncer
# 
# Usage:
#   pyinstaller helloasso_syncer.spec
#
# This will create a standalone executable in the dist/ directory

block_cipher = None

# Application information
a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include all GUI styles
        ('gui/styles/styles.css', 'gui/styles'),
        
        # Include data files
        ('secrets.template.json', '.'),
        ('requirements.txt', '.'),
        ('requirements-gui.txt', '.'),
        ('Readme.md', '.'),
    ],
    hiddenimports=[
        'helloasso',
        'helloasso.client',
        'helloasso.config',
        'helloasso.config_manager',
        'helloasso.export',
        'helloasso.models',
        'helloasso.models.schemas',
        'helloasso.reporter',
        'helloasso.syncer',
        'gui',
        'gui.dialogs',
        'gui.main',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PyInstaller doesn't know about Qt6 plugins, so we need to collect them manually
# This includes the platforms, styles, and other Qt plugins
a.datas += [
    # Qt6 plugins
    ('C:/Python310/Lib/site-packages/PySide6/Qt6/plugins/platforms/qwindows.dll', 'platforms'),
    ('C:/Python310/Lib/site-packages/PySide6/Qt6/plugins/styles/qwindowsvista.dll', 'styles'),
    
    # Also try common Qt plugin locations
]

# Collect Qt6 translations
a.datas += [
    ('C:/Python310/Lib/site-packages/PySide6/Qt6/translations/qtbase_*.qm', 'translations'),
]

# Custom handling for Qt6 plugins - we'll use a runtime hook
# to set the QT_QPA_PLATFORM_PLUGIN_PATH environment variable

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

ex = Executable(
    'run.py',
    targets=[
        Target(
            name='HelloAssoSyncer',
            script='run.py',
            icon=None,  # Add icon path here if you have one
            version='1.0.0',
            company='Aviron Club Angoulême',
            copyright='Copyright © 2026 Aviron Club Angoulême',
            trademarks=None,
            product_name='HelloAsso Syncer',
            internal_name='HelloAssoSyncer',
            file_version='1.0.0',
            product_version='1.0.0',
            description='Synchronisation tool for HelloAsso data',
            author='Aviron Club Angoulême',
            author_email=None,
            url=None,
            license=None,
            language=None,
        )
    ],
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed application (no console)
    argv_emulation=False,
    pre_safe_import_module=False,
)

# Create a coll object for the Qt plugins
# We'll collect them from the PySide6 installation
import sys
import os

# Try to find Qt6 plugins directory
qt_plugins_paths = []
if sys.platform == 'win32':
    # Common PySide6 plugin locations on Windows
    pyside6_paths = [
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PySide6', 'Qt6', 'plugins'),
        os.path.join(sys.prefix, 'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins'),
        'C:/Python310/Lib/site-packages/PySide6/Qt6/plugins',
        'C:/Python39/Lib/site-packages/PySide6/Qt6/plugins',
    ]
    for path in pyside6_paths:
        if os.path.exists(path):
            qt_plugins_paths.append(path)
            break

# Add Qt plugins to the spec
for plugin_dir in qt_plugins_paths:
    for root, dirs, files in os.walk(plugin_dir):
        for file in files:
            src = os.path.join(root, file)
            dst = os.path.join('platforms' if 'platforms' in root else 
                             'styles' if 'styles' in root else 
                             os.path.basename(root), file)
            a.datas += [(src, dst)]

# Also collect translations
for plugin_dir in qt_plugins_paths:
    trans_dir = os.path.join(os.path.dirname(plugin_dir), 'translations')
    if os.path.exists(trans_dir):
        for file in os.listdir(trans_dir):
            if file.endswith('.qm'):
                a.datas += [(os.path.join(trans_dir, file), 'translations')]

coll = COLLECT(
    ex,
    a.pure,
    a.zipped_data,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HelloAssoSyncer',
)
