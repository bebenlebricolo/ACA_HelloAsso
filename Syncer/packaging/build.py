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

import sys
import subprocess
import shutil
import os
from pathlib import Path

def get_qt_plugin_paths():
    """Get all Qt6 plugin files that need to be included."""
    plugin_files = []

    # Check .venv first
    venv_qt_path = Path.cwd() / ".venv" / "Lib" / "site-packages" / "PySide6" / "Qt6" / "plugins"
    if venv_qt_path.exists():
        for plugin_type in ['platforms', 'styles', 'imageformats', 'iconengines', 'tls']:
            plugin_dir = venv_qt_path / plugin_type
            if plugin_dir.exists():
                for plugin_file in plugin_dir.glob("*"):
                    if plugin_file.is_file():
                        plugin_files.append(str(plugin_file))

        # Add translations
        trans_dir = venv_qt_path.parent / "translations"
        if trans_dir.exists():
            for trans_file in trans_dir.glob("qt*_*.qm"):
                plugin_files.append(str(trans_file))

    # Also check system-wide PySide6
    for prefix in [sys.prefix, "C:/Python310", "C:/Python311", "C:/Python312"]:
        qt_path = Path(prefix) / "Lib" / "site-packages" / "PySide6" / "Qt6" / "plugins"
        if qt_path.exists():
            for plugin_type in ['platforms', 'styles', 'imageformats', 'iconengines', 'tls']:
                plugin_dir = qt_path / plugin_type
                if plugin_dir.exists():
                    for plugin_file in plugin_dir.glob("*"):
                        if plugin_file.is_file():
                            plugin_files.append(str(plugin_file))

            # Add translations
            trans_dir = qt_path.parent / "translations"
            if trans_dir.exists():
                for trans_file in trans_dir.glob("qt*_*.qm"):
                    plugin_files.append(str(trans_file))

    return plugin_files


def build():
    """Build the executable using PyInstaller."""
    ROOT_DIR = Path(__file__).parent.parent
    BUILD_DIR = ROOT_DIR / "build"
    DIST_DIR = ROOT_DIR / "dist"
    APP_ICON = ROOT_DIR / "assets" / "app_icon.png"

    print("Building HelloAsso Syncer...")
    print(f"Root directory: {ROOT_DIR}")

    # Ensure directories exist
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)

    # Get Qt plugin paths
    qt_files = get_qt_plugin_paths()
    print(f"Found {len(qt_files)} Qt plugin files")

    # Base command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=HelloAssoSyncer",
        "--windowed",  # No console
        "--clean",
        "--distpath=" + str(DIST_DIR),
        "--workpath=" + str(BUILD_DIR),
        "--onefile",  # Create a single executable file for easy distribution
        f"--icon={APP_ICON}",
        "--noconfirm",  # Don't ask for confirmation
    ]

    # Add Qt plugin files
    for qt_file in qt_files:
        # Extract the plugin type from the path
        if "platforms" in qt_file:
            dest = "platforms"
        elif "styles" in qt_file:
            dest = "styles"
        elif "imageformats" in qt_file:
            dest = "imageformats"
        elif "iconengines" in qt_file:
            dest = "iconengines"
        elif "tls" in qt_file:
            dest = "tls"
        elif "translations" in qt_file:
            dest = "translations"
        else:
            dest = "qt_plugins"
        cmd.append(f"--add-data={qt_file}:{dest}")

    # Add our application data files
    app_data_files = [
        ("gui/styles/styles.css", "gui/styles"),
        ("secrets.template.json", "."),
        ("Readme.md", "."),
    ]

    for src, dst in app_data_files:
        full_src = ROOT_DIR / src
        if full_src.exists():
            cmd.append(f"--add-data={full_src}:{dst}")

    # Add the main script
    cmd.append("run.py")

    print("Running command:")
    print(" ".join(cmd))
    print()

    # Change to root directory and run
    original_cwd = os.getcwd()
    try:
        os.chdir(ROOT_DIR)
        result = subprocess.run(cmd, check=True)
        print("Build completed successfully!")
        print(f"Executable created in: {DIST_DIR / 'HelloAssoSyncer.exe'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return False
    finally:
        os.chdir(original_cwd)


def create_archive():
    """Create a zip archive of the distribution."""
    ROOT_DIR = Path(__file__).parent.parent
    DIST_DIR = ROOT_DIR / "dist"

    archive_name = DIST_DIR / "HelloAssoSyncer-1.0.0-windows.zip"

    print(f"\nCreating archive: {archive_name}")

    try:
        # Remove existing archive if it exists
        if archive_name.exists():
            archive_name.unlink()

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
    ROOT_DIR = Path(__file__).parent.parent

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
    print("The self-contained executable is ready for distribution!")
    print("Users can extract the zip file and run HelloAssoSyncer.exe")
    print("=" * 60)


if __name__ == "__main__":
    main()