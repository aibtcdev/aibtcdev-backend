#!/usr/bin/env python
"""
This script checks the organization of the project to ensure that all components
are properly organized according to the new structure.
"""

import importlib
import sys
from pathlib import Path


def check_imports():
    """Check if all the required modules can be imported correctly."""
    try:
        # Core components
        import config
        from config import config as config_instance

        print("✅ config module imported successfully")

        # API components
        import api.chat
        from api.chat import router as chat_router

        print("✅ api.chat module imported successfully")

        # Services components
        import services.websocket
        from services.websocket import websocket_manager

        print("✅ services.websocket module imported successfully")

        import services.chat
        from services.chat import ChatService

        print("✅ services.chat module imported successfully")

        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def check_structure():
    """Check if the file structure is correct."""
    base_path = Path(__file__).parent

    # Check for required files
    required_files = [
        "services/websocket.py",
        "services/chat.py",
        "api/chat.py",
        "main.py",
        "config.py",
    ]

    all_exist = True
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} does not exist")
            all_exist = False

    # Check for old files that should be removed
    old_files = ["lib/websocket_manager.py"]

    for file_path in old_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"❌ {file_path} should be removed")
            all_exist = False
        else:
            print(f"✅ {file_path} correctly removed")

    return all_exist


if __name__ == "__main__":
    print("🔍 Checking project organization...")
    print("\n=== File Structure ===")
    structure_ok = check_structure()

    print("\n=== Import Checks ===")
    imports_ok = check_imports()

    if structure_ok and imports_ok:
        print("\n✅ All checks passed! Project organization is correct.")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)
