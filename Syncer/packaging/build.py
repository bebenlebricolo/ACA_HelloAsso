#!/usr/bin/env python3
"""
Build script for HelloAsso Syncer

This script creates a standalone executable using PyInstaller.

Requirements:
    pip install pyinstaller

Usage:
    python build.py
    
This will create the executable in the dist/ directory.
"""

import os
import sys
import subprocess
from pathlib import Path

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent

# Output directories
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"

# Ensure directories exist
BUILD_DIR.mkdir(exist_ok=True)
DIST_DIR.mkdir(exist_ok=True)

# Qt plugin directories to collect
QT_PLUGIN_DIRS = [
    "platforms",
    "styles",
    "imageformats",
    "iconengines",
]


def find_qt_plugins():
    """Find Qt6 plugins from PySide6 installation."""
    import site
    
    plugins_dirs = []
    
    # Common locations for PySide6 Qt6 plugins
    possible_paths = [
        # Windows
        Path(sys.prefix) / "Lib" / "site-packages" / "PySide6" / "Qt6" / "plugins",
        Path(sys.prefix) / "Lib" / "site-packages" / "PyQt6" / "Qt6" / "plugins",
        # macOS/Linux
        Path(sys.prefix) / "lib" / "python" / f"{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "PySide6" / "Qt6" / "plugins",
    ]
    
    for path in possible_paths:
        if path.exists():
            plugins_dirs.append(path)
    
    return plugins_dirs


def collect_qt_data_args():
    """Collect Qt plugin files for PyInstaller."""
    data_args = []
    
    plugins_dirs = find_qt_plugins()
    
    for plugins_dir in plugins_dirs:
        for plugin_type in QT_PLUGIN_DIRS:
            plugin_path = plugins_dir / plugin_type
            if plugin_path.exists():
                for plugin_file in plugin_path.glob("*"):
                    if plugin_file.is_file():
                        # Use relative path for the destination
                        data_args.append(f"--add-data={plugin_file}:{plugin_type}")
    
    # Also add translations
    for plugins_dir in plugins_dirs:
        trans_dir = plugins_dir.parent / "translations"
        if trans_dir.exists():
            for trans_file in trans_dir.glob("qt*_*.qm"):
                data_args.append(f"--add-data={trans_file}:translations")
    
    return data_args


def build():
    """Build the executable using PyInstaller."""
    print("Building HelloAsso Syncer...")
    print(f"Root directory: {ROOT_DIR}")
    
    # Find Qt plugins and build data arguments
    qt_data_args = collect_qt_data_args()
    
    # Base command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=HelloAssoSyncer",
        "--windowed",  # No console
        "--version=1.0.0",
        "--company=Aviron Club Angoulême",
        "--product-name=HelloAsso Syncer",
        "--description=Synchronisation tool for HelloAsso data",
        "--author=Aviron Club Angoulême",
        "--clean",
        "--distpath=dist",
        "--workpath=build",
        "--specpath=build",
        "--upx-dir=",  # Disable UPX by default (can be slow)
    ]
    
    # Add Qt data
    cmd.extend(qt_data_args)
    
    # Add our application data files
    app_data_files = [
        "gui/styles/styles.css:gui/styles",
        "secrets.template.json:.",
        "Readme.md:.",
    ]
    
    for data_file in app_data_files:
        src, dst = data_file.split(":")
        full_src = ROOT_DIR / src
        if full_src.exists():
            cmd.append(f"--add-data={full_src}:{dst}")
    
    # Add the main script
    cmd.append("run.py")
    
    print("Running command:")
    print(" ".join(cmd))
    print()
    
    # Run the command
    try:
        result = subprocess.run(cmd, cwd=ROOT_DIR, check=True)
        print("Build completed successfully!")
        print(f"Executable created in: {DIST_DIR / 'HelloAssoSyncer'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return False


def create_archive():
    """Create a zip archive of the distribution."""
    import shutil
    
    archive_name = DIST_DIR / "HelloAssoSyncer-1.0.0-windows.zip"
    
    print(f"\nCreating archive: {archive_name}")
    
    try:
        shutil.make_archive(
            str(archive_name.with_suffix('')),
            'zip',
            DIST_DIR
        )
        print(f"Archive created: {archive_name}")
        return True
    except Exception as e:
        print(f"Failed to create archive: {e}")
        return False


def main():
    print("=" * 60)
    print("HelloAsso Syncer - Build Script")
    print("=" * 60)
    print()
    
    # Check for PyInstaller
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller is not installed!")
        print("Please install it first:")
        print("  pip install pyinstaller")
        sys.exit(1)
    
    # Build the executable
    if not build():
        sys.exit(1)
    
    # Create archive
    if not create_archive():
        print("Warning: Archive creation failed, but executable was built")
    
    print("\n" + "=" * 60)
    print("Build process completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
