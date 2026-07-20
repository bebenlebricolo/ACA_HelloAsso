# Packaging HelloAsso Syncer

This directory contains the tools needed to package HelloAsso Syncer into a standalone executable that can be distributed to end users.

## Prerequisites

To build the package, you need:

1. **Python 3.8+** installed on your build machine
2. **PyInstaller** installed:
   ```bash
   pip install pyinstaller
   ```
3. **PySide6** installed (should already be in your development environment)
4. **All other dependencies** from `requirements-gui.txt`

## Quick Build

The easiest way to build is using the provided batch file:

### On Windows:
```batch
cd packaging
build.bat
```

Or manually:
```bash
python build.py
```

This will:
1. Create a standalone executable `HelloAssoSyncer.exe` in the `dist/` directory
2. Package all required files (Python interpreter, Qt libraries, etc.)
3. Create a zip archive for easy distribution

## Manual PyInstaller Command

If you prefer to run PyInstaller directly, use this command from the `Syncer/` directory:

```bash
pyinstaller \
    --name=HelloAssoSyncer \
    --windowed \
    --add-data="gui/styles/styles.css:gui/styles" \
    --add-data="secrets.template.json:." \
    --add-data="Readme.md:." \
    --icon=assets/icon.ico \  # Optional: add your icon
    run.py
```

**Important**: You must also include Qt6 plugins. See below.

## Including Qt6 Plugins

PyInstaller doesn't automatically include Qt6 plugins, which are required for the GUI to work. The build script automatically finds and includes:

- `platforms/qwindows.dll` (required for Windows)
- `styles/qwindowsvista.dll` (for native styling)
- Other plugin directories

If you encounter Qt plugin errors, you can manually specify the plugins:

```bash
--add-data="C:/Python310/Lib/site-packages/PySide6/Qt6/plugins/platforms/qwindows.dll:platforms"
```

Adjust the path to match your Python installation.

## Build Output

After building, you'll find:

```
Syncer/
├── build/               # Temporary build files (can be deleted)
└── dist/
    ├── HelloAssoSyncer/ # The packaged application
    │   ├── HelloAssoSyncer.exe
    │   ├── _internal/   # All bundled files
    │   ├── gui/
    │   │   └── styles/
    │   │       └── styles.css
    │   ├── platforms/
    │   │   └── qwindows.dll
    │   ├── styles/
    │   │   └── qwindowsvista.dll
    │   ├── secrets.template.json
    │   └── Readme.md
    └── HelloAssoSyncer-1.0.0-windows.zip  # Optional archive
```

## Distribution

### Option 1: Single Executable (Recommended)

The `dist/HelloAssoSyncer` directory contains everything needed. You can:

1. **Zip the entire directory** and distribute it
2. **Use the pre-built zip archive** from `dist/HelloAssoSyncer-1.0.0-windows.zip`

### Option 2: Single EXE File

If you want a true single-file executable (larger file, slower startup):

```bash
pyinstaller --onefile run.py
```

This creates a single `HelloAssoSyncer.exe` file in the `dist/` directory.

## Testing the Package

After building, test the executable:

```bash
cd dist/HelloAssoSyncer
HelloAssoSyncer.exe
```

The first time you run it, you should see the first-run configuration dialog asking for Client ID and Client Secret.

## Troubleshooting

### "Failed to execute script" error

This usually means a missing Qt plugin. Make sure you've included all Qt6 plugins in the build.

### "No module named 'PySide6'" error

The PyInstaller analysis might have missed some hidden imports. Add them to the spec file:

```python
hiddenimports=[
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    # ... etc
]
```

### Application doesn't start

Check if there's a console window flashing briefly. Run from command line to see errors:

```bash
cd dist/HelloAssoSyncer
HelloAssoSyncer.exe --cli
```

### Large file size

The bundled executable is large (~50-100MB) because it includes:
- Python interpreter
- PySide6/Qt6 libraries
- All dependencies

This is normal for a standalone Python + Qt application.

## Advanced Customization

### Adding an Icon

1. Create or obtain an `.ico` file (e.g., `icon.ico`)
2. Place it in the `assets/` directory
3. Update the build script or use:
   ```bash
   pyinstaller --icon=assets/icon.ico run.py
   ```

### Version Information (Windows)

You can add detailed version information:

```bash
pyinstaller \
    --name=HelloAssoSyncer \
    --version=1.0.0 \
    --company="Aviron Club Angoulême" \
    --product-name="HelloAsso Syncer" \
    --product-version=1.0.0 \
    --file-version=1.0.0 \
    --copyright="Copyright © 2026 Aviron Club Angoulême" \
    run.py
```

### Code Signing (Windows)

For professional distribution, consider code signing your executable to avoid security warnings.

## For End Users

End users don't need Python or any other dependencies installed. They just need to:

1. Extract the zip file
2. Double-click `HelloAssoSyncer.exe`
3. Enter their Client ID and Client Secret on first launch
4. Click "Save" to save the configuration

The configuration is saved next to the executable (and optionally in AppData for persistence).
