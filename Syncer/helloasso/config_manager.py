"""
Configuration file management for HelloAsso Syncer.

Handles loading and saving configuration to both local files and AppData.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any


# Configuration file names
SECRETS_FILENAME = "secrets.json"
CONFIG_FILENAME = "config.json"


def get_appdata_path() -> Optional[Path]:
    """Get the AppData directory path for the application."""
    if sys.platform == "win32":
        import ctypes.wintypes
        # Get AppData\Roaming path
        CSIDL_APPDATA = 0x001a
        buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_APPDATA, None, 0, buffer)
        appdata = Path(buffer.value) / "HelloAssoSyncer"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/HelloAssoSyncer
        appdata = Path.home() / "Library" / "Application Support" / "HelloAssoSyncer"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata
    elif sys.platform == "linux":
        # Linux: ~/.config/HelloAssoSyncer
        appdata = Path.home() / ".config" / "HelloAssoSyncer"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata
    return None


def get_executable_path() -> Path:
    """Get the directory where the executable is located."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent


def get_config_path(local: bool = True) -> Path:
    """Get the path to the configuration directory."""
    if local:
        return get_executable_path()
    else:
        appdata = get_appdata_path()
        return appdata if appdata else get_executable_path()


def get_secrets_path(local: bool = True) -> Path:
    """Get the path to the secrets file."""
    return get_config_path(local) / SECRETS_FILENAME


def get_config_file_path(local: bool = True) -> Path:
    """Get the path to the config file."""
    return get_config_path(local) / CONFIG_FILENAME


def config_exists(local: bool = True, appdata: bool = True) -> bool:
    """Check if configuration files exist."""
    if local:
        local_secrets = get_secrets_path(local=True)
        local_config = get_config_file_path(local=True)
        if local_secrets.exists() or local_config.exists():
            return True

    if appdata:
        appdata_secrets = get_secrets_path(local=False)
        appdata_config = get_config_file_path(local=False)
        if appdata_secrets.exists() or appdata_config.exists():
            return True

    return False


def load_config(local: bool = True, appdata: bool = True) -> Optional[Dict[str, Any]]:
    """
    Load configuration from files.

    Tries local first, then AppData. Merges both if they exist.
    Returns None if no config found.
    """
    config = {}

    # Try local
    if local:
        local_config_path = get_config_file_path(local=True)
        local_secrets_path = get_secrets_path(local=True)

        if local_secrets_path.exists():
            try:
                with open(local_secrets_path, 'r', encoding='utf-8') as f:
                    secrets = json.load(f)
                    config.update(secrets)
            except (json.JSONDecodeError, IOError):
                pass

        if local_config_path.exists():
            try:
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
                    config.update(local_config)
            except (json.JSONDecodeError, IOError):
                pass

    # Try AppData
    if appdata:
        appdata_path = get_appdata_path()
        if appdata_path:
            appdata_config_path = get_config_file_path(local=False)
            appdata_secrets_path = get_secrets_path(local=False)

            if appdata_secrets_path.exists():
                try:
                    with open(appdata_secrets_path, 'r', encoding='utf-8') as f:
                        secrets = json.load(f)
                        # AppData takes precedence for secrets
                        config.update(secrets)
                except (json.JSONDecodeError, IOError):
                    pass

            if appdata_config_path.exists():
                try:
                    with open(appdata_config_path, 'r', encoding='utf-8') as f:
                        appdata_config = json.load(f)
                        # Merge, with AppData taking precedence
                        config.update(appdata_config)
                except (json.JSONDecodeError, IOError):
                    pass

    return config if config else None


def save_config(data: Dict[str, Any], local: bool = True, appdata: bool = True) -> bool:
    """
    Save configuration to files.

    Separates secrets (client_id, client_secret) from other config.
    Can save to local directory, AppData, or both.
    """
    # Separate secrets from other config
    secrets = {}
    other_config = {}

    for key, value in data.items():
        if key in ('client_id', 'client_secret', 'clientId', 'clientSecret'):
            secrets[key] = value
        else:
            other_config[key] = value

    success = True

    # Save to local
    if local:
        local_dir = get_executable_path()
        local_dir.mkdir(parents=True, exist_ok=True)

        # Save secrets
        local_secrets_path = local_dir / SECRETS_FILENAME
        try:
            with open(local_secrets_path, 'w', encoding='utf-8') as f:
                json.dump(secrets, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving local secrets: {e}")
            success = False

        # Save config
        local_config_path = local_dir / CONFIG_FILENAME
        try:
            with open(local_config_path, 'w', encoding='utf-8') as f:
                json.dump(other_config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving local config: {e}")
            success = False

    # Save to AppData
    if appdata:
        appdata_dir = get_appdata_path()
        if appdata_dir:
            appdata_dir.mkdir(parents=True, exist_ok=True)

            # Save secrets
            appdata_secrets_path = appdata_dir / SECRETS_FILENAME
            try:
                with open(appdata_secrets_path, 'w', encoding='utf-8') as f:
                    json.dump(secrets, f, indent=2, ensure_ascii=False)
            except IOError as e:
                print(f"Error saving AppData secrets: {e}")
                success = False

            # Save config
            appdata_config_path = appdata_dir / CONFIG_FILENAME
            try:
                with open(appdata_config_path, 'w', encoding='utf-8') as f:
                    json.dump(other_config, f, indent=2, ensure_ascii=False)
            except IOError as e:
                print(f"Error saving AppData config: {e}")
                success = False

    return success


def delete_config(local: bool = True, appdata: bool = True) -> None:
    """Delete configuration files."""
    if local:
        local_secrets = get_secrets_path(local=True)
        local_config = get_config_file_path(local=True)

        if local_secrets.exists():
            local_secrets.unlink()
        if local_config.exists():
            local_config.unlink()

    if appdata:
        appdata_secrets = get_secrets_path(local=False)
        appdata_config = get_config_file_path(local=False)

        if appdata_secrets.exists():
            appdata_secrets.unlink()
        if appdata_config.exists():
            appdata_config.unlink()
