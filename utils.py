from cryptography.fernet import Fernet
import os
import base64
from typing import Optional


class EncryptionManager:
    def __init__(self):
        self.key = os.getenv("ENCRYPTION_KEY")
        if not self.key:
            raise ValueError("ENCRYPTION_KEY environment variable is required")

        # Ensure the key is properly formatted for Fernet
        try:
            self.fernet = Fernet(
                self.key.encode() if isinstance(self.key, str) else self.key
            )
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}")

    def encrypt(self, data: str) -> bytes:
        """Encrypt a string using Fernet symmetric encryption"""
        if not data:
            raise ValueError("Data to encrypt cannot be empty")

        try:
            # Convert string to bytes, encrypt, and return bytes
            data_bytes = data.encode("utf-8")
            encrypted_data = self.fernet.encrypt(data_bytes)
            return encrypted_data
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt bytes back to a string using Fernet"""
        if not encrypted_data:
            raise ValueError("Encrypted data cannot be empty")

        try:
            decrypted_bytes = self.fernet.decrypt(encrypted_data)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key for encryption"""
        return Fernet.generate_key().decode("utf-8")

    def validate_key(self) -> bool:
        """Validate that the current key can encrypt/decrypt data"""
        try:
            test_data = "test"
            encrypted = self.encrypt(test_data)
            decrypted = self.decrypt(encrypted)
            return decrypted == test_data
        except Exception:
            return False
