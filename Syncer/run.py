#!/usr/bin/env python3
"""
HelloAsso Syncer - Main entry point

This script provides a unified entry point for both CLI and GUI modes.

Usage:
    # Launch GUI (default)
    python run.py
    
    # Launch GUI explicitly
    python run.py --gui
    
    # Launch CLI with arguments
    python run.py --cli --forms licence-jeunes-saison-25-26
    
    # Or use the old way
    python helloasso/syncer.py --forms all
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="HelloAsso Syncer - Synchronize payments and memberships"
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gui",
        action="store_true",
        default=True,
        help="Launch the graphical user interface (default)"
    )
    mode_group.add_argument(
        "--cli",
        action="store_true",
        help="Use command-line interface"
    )
    
    # Parse known args first to check for mode
    known_args, remaining_args = parser.parse_known_args()
    
    if known_args.gui or (not known_args.cli and not remaining_args):
        # Launch GUI
        from gui.main import main as gui_main
        sys.argv = [sys.argv[0]]  # Reset argv for Qt
        gui_main()
    else:
        # Launch CLI - pass remaining args
        sys.argv = [sys.argv[0]] + remaining_args
        from helloasso.syncer import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
