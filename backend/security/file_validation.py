"""File validation: type checking, magic bytes, size limits."""

import magic
from fastapi import UploadFile, HTTPException
from config import settings

# Allowed MIME types and their extensions
ALLOWED_TYPES = {
    "application/pdf": [".pdf"],
    "image/png": [".png"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/tiff": [".tiff", ".tif"],
    "image/bmp": [".bmp"],
    "text/plain": [".txt", ".md", ".csv"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
}

# Flatten for quick lookup
ALLOWED_EXTENSIONS = set()
for exts in ALLOWED_TYPES.values():
    ALLOWED_EXTENSIONS.update(exts)

# Maximum file sizes per type (in bytes)
MAX_SIZES = {
    "application/pdf": settings.max_file_size_mb * 1024 * 1024,
    "image/png": 20 * 1024 * 1024,  # 20MB for images
    "image/jpeg": 20 * 1024 * 1024,
    "image/tiff": 30 * 1024 * 1024,
    "image/bmp": 30 * 1024 * 1024,
    "text/plain": 10 * 1024 * 1024,  # 10MB for text
}


async def validate_file(file: UploadFile) -> tuple[bytes, str]:
    """
    Validate an uploaded file for security.
    
    Returns:
        Tuple of (file_bytes, detected_mime_type)
        
    Raises:
        HTTPException if validation fails
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    # Check extension
    filename_lower = file.filename.lower()
    ext = ""
    if "." in filename_lower:
        ext = "." + filename_lower.rsplit(".", 1)[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file content
    content = await file.read()
    await file.seek(0)

    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    # Check file size
    file_size = len(content)
    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({file_size // (1024*1024)}MB) exceeds maximum ({settings.max_file_size_mb}MB)",
        )

    # Verify MIME type using magic bytes (not just extension)
    detected_mime = magic.from_buffer(content, mime=True)

    if detected_mime not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Detected file type '{detected_mime}' is not allowed. The file extension may not match its actual content.",
        )

    # Verify extension matches detected MIME
    if ext and ext not in ALLOWED_TYPES.get(detected_mime, []):
        # Allow some flexibility (e.g., .txt detected as various text types)
        if not (detected_mime.startswith("text/") and ext in [".txt", ".md", ".csv"]):
            raise HTTPException(
                status_code=400,
                detail=f"File extension '{ext}' does not match detected type '{detected_mime}'. Possible file spoofing.",
            )

    # Check type-specific size limits
    type_max = MAX_SIZES.get(detected_mime, max_size)
    if file_size > type_max:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds limit for type '{detected_mime}' ({type_max // (1024*1024)}MB)",
        )

    return content, detected_mime
