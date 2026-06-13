"""
Secure Storage Service.

Handles encrypted file storage, retrieval, and cleanup.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

from config import settings
from security.encryption import encryptor

logger = logging.getLogger(__name__)


class StorageService:
    """Manages encrypted document and page image storage."""

    def store_document(self, file_data: bytes, original_filename: str) -> tuple[str, str]:
        """
        Store a document file with encryption.
        
        Returns:
            Tuple of (stored_filename, file_hash)
        """
        # Generate unique filename
        ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
        stored_filename = f"{uuid.uuid4().hex}.{ext}.enc"

        # Compute hash before encryption
        file_hash = encryptor.compute_file_hash(file_data)

        # Encrypt and store
        encrypted_data = encryptor.encrypt_file(file_data)
        file_path = settings.documents_path / stored_filename

        with open(file_path, "wb") as f:
            f.write(encrypted_data)

        logger.info(f"Stored document: {stored_filename} ({len(file_data)} bytes)")
        return stored_filename, file_hash

    def retrieve_document(self, stored_filename: str) -> bytes:
        """Retrieve and decrypt a stored document."""
        file_path = settings.documents_path / stored_filename

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {stored_filename}")

        with open(file_path, "rb") as f:
            encrypted_data = f.read()

        return encryptor.decrypt_file(encrypted_data)

    def store_page_image(self, image_data: bytes, document_id: str, page_number: int) -> str:
        """
        Store a page image with encryption.
        
        Returns:
            Image filename
        """
        image_filename = f"{document_id}_page_{page_number}.png.enc"

        # Encrypt and store
        encrypted_data = encryptor.encrypt_file(image_data)
        file_path = settings.page_images_path / image_filename

        with open(file_path, "wb") as f:
            f.write(encrypted_data)

        return image_filename

    def retrieve_page_image(self, image_filename: str) -> bytes:
        """Retrieve and decrypt a page image."""
        file_path = settings.page_images_path / image_filename

        if not file_path.exists():
            raise FileNotFoundError(f"Page image not found: {image_filename}")

        with open(file_path, "rb") as f:
            encrypted_data = f.read()

        return encryptor.decrypt_file(encrypted_data)

    def delete_document_files(self, stored_filename: str, document_id: str):
        """Delete all files associated with a document."""
        # Delete the document file
        doc_path = settings.documents_path / stored_filename
        if doc_path.exists():
            os.remove(doc_path)
            logger.info(f"Deleted document file: {stored_filename}")

        # Delete all page images for this document
        for img_file in settings.page_images_path.glob(f"{document_id}_page_*.png.enc"):
            os.remove(img_file)
            logger.info(f"Deleted page image: {img_file.name}")

    def get_storage_stats(self) -> dict:
        """Get storage usage statistics."""
        doc_count = len(list(settings.documents_path.glob("*.enc")))
        img_count = len(list(settings.page_images_path.glob("*.enc")))

        doc_size = sum(f.stat().st_size for f in settings.documents_path.glob("*.enc"))
        img_size = sum(f.stat().st_size for f in settings.page_images_path.glob("*.enc"))

        return {
            "document_files": doc_count,
            "page_images": img_count,
            "total_size_mb": round((doc_size + img_size) / (1024 * 1024), 2),
        }


# Singleton
storage_service = StorageService()
