#!/usr/bin/env python3
"""
Quick test script to verify AIO Discord Bot setup
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_environment():
    """Test if all required environment variables are set"""
    print("Testing Environment Variables...")

    required_vars = {
        "DISCORD_TOKEN": "Discord Bot Token",
        "ENCRYPTION_KEY": "Fernet Encryption Key",
        "DATABASE_URL": "PostgreSQL Database URL",
    }

    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            if var == "DISCORD_TOKEN":
                print(f"[OK] {description}: {'*' * 10}...{value[-4:]}")
            elif var == "ENCRYPTION_KEY":
                print(f"[OK] {description}: {value[:10]}...{value[-10:]}")
            else:
                print(f"[OK] {description}: {value[:30]}...")
        else:
            print(f"[FAIL] {description}: NOT SET")
            all_set = False

    return all_set


def test_imports():
    """Test if all required modules can be imported"""
    print("\nTesting Module Imports...")

    modules = [
        ("discord", "Discord API wrapper"),
        ("asyncpg", "Async PostgreSQL driver"),
        ("cryptography", "Encryption library"),
        ("yt_dlp", "YouTube/SoundCloud downloader"),
        ("mutagen", "Audio metadata handler"),
        ("requests", "HTTP client"),
        ("aiohttp", "Async HTTP client"),
    ]

    all_imported = True
    for module, description in modules:
        try:
            __import__(module)
            print(f"[OK] {description}")
        except ImportError as e:
            print(f"[FAIL] {description}: {e}")
            all_imported = False

    return all_imported


def test_encryption():
    """Test encryption/decryption functionality"""
    print("\nTesting Encryption...")

    try:
        from cryptography.fernet import Fernet
        from utils import EncryptionManager

        # Test encryption manager
        enc_manager = EncryptionManager()
        test_data = "test_password_123"

        encrypted = enc_manager.encrypt(test_data)
        decrypted = enc_manager.decrypt(encrypted)

        if decrypted == test_data:
            print("[OK] Encryption/Decryption working correctly")
            return True
        else:
            print("[FAIL] Encryption/Decryption failed")
            return False

    except Exception as e:
        print(f"[FAIL] Encryption test failed: {e}")
        return False


def test_database_config():
    """Test database configuration"""
    print("\nTesting Database Configuration...")

    try:
        from database import DatabaseManager

        db_manager = DatabaseManager()
        print(f"[OK] Database URL configured: {db_manager.database_url[:50]}...")
        return True

    except Exception as e:
        print(f"[FAIL] Database configuration failed: {e}")
        return False


def main():
    """Run all tests"""
    print("AIO Discord Bot - Setup Verification\n")

    tests = [
        ("Environment Variables", test_environment),
        ("Module Imports", test_imports),
        ("Encryption", test_encryption),
        ("Database Config", test_database_config),
    ]

    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))

    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:.<30} {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("ALL TESTS PASSED! Bot is ready for deployment.")
        print("\nNext steps:")
        print("1. Add your Discord token to .env file")
        print("2. Push to GitHub")
        print("3. Deploy to Railway")
        print("4. Test bot functionality")
    else:
        print("Some tests failed. Please fix issues before deploying.")

    print("=" * 50)


if __name__ == "__main__":
    main()
