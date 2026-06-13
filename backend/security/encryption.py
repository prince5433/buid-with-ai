"""AES-256-GCM encryption for secure file storage."""

import os
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from config import settings


class FileEncryptor:
    """Handles AES-256-GCM encryption/decryption of files with HMAC integrity."""

    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32  # 256 bits
    HMAC_SIZE = 32

    def __init__(self):
        self._master_key = self._derive_master_key()

    def _derive_master_key(self) -> bytes:
        """Derive encryption key from environment variable using PBKDF2."""
        key_material = settings.encryption_key.encode('utf-8')
        # Use a fixed salt derived from the key itself for deterministic key derivation
        salt = hashlib.sha256(key_material).digest()[:self.SALT_SIZE]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(key_material)

    def encrypt_file(self, file_data: bytes) -> bytes:
        """
        Encrypt file data using AES-256-GCM.
        
        Returns: salt (16) + nonce (12) + ciphertext + HMAC (32)
        """
        salt = os.urandom(self.SALT_SIZE)
        nonce = os.urandom(self.NONCE_SIZE)

        # Derive a unique key for this file using the salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=100_000,
        )
        file_key = kdf.derive(self._master_key)

        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(file_key)
        ciphertext = aesgcm.encrypt(nonce, file_data, None)

        # Create HMAC for integrity verification
        encrypted_payload = salt + nonce + ciphertext
        file_hmac = hmac.new(
            self._master_key, encrypted_payload, hashlib.sha256
        ).digest()

        return encrypted_payload + file_hmac

    def decrypt_file(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt file data and verify HMAC integrity.
        
        Raises ValueError if integrity check fails.
        """
        if len(encrypted_data) < self.SALT_SIZE + self.NONCE_SIZE + self.HMAC_SIZE + 16:
            raise ValueError("Invalid encrypted data: too short")

        # Split components
        stored_hmac = encrypted_data[-self.HMAC_SIZE:]
        encrypted_payload = encrypted_data[:-self.HMAC_SIZE]

        # Verify HMAC integrity
        computed_hmac = hmac.new(
            self._master_key, encrypted_payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(stored_hmac, computed_hmac):
            raise ValueError("File integrity check failed — data may be tampered")

        # Extract components
        salt = encrypted_payload[:self.SALT_SIZE]
        nonce = encrypted_payload[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
        ciphertext = encrypted_payload[self.SALT_SIZE + self.NONCE_SIZE:]

        # Derive file key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=100_000,
        )
        file_key = kdf.derive(self._master_key)

        # Decrypt
        aesgcm = AESGCM(file_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    @staticmethod
    def compute_file_hash(file_data: bytes) -> str:
        """Compute SHA-256 hash of file for deduplication and tracking."""
        return hashlib.sha256(file_data).hexdigest()


# Singleton
encryptor = FileEncryptor()
