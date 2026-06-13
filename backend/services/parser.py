"""
Document Parser Service.

Handles parsing of PDFs (digital & scanned), images, and text files.
Extracts text and renders page images for each page.
"""

import io
import logging
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pdfplumber
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import pytesseract

from config import settings
from security.encryption import encryptor

logger = logging.getLogger(__name__)

# Try to use pdf2image, but have a fallback via PyMuPDF
try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except Exception:
    HAS_PDF2IMAGE = False
    logger.warning("pdf2image not available, falling back to PyMuPDF for page rendering")


class ParsedPage:
    """Result of parsing a single page."""

    def __init__(
        self,
        page_number: int,
        text: str,
        image_bytes: Optional[bytes] = None,
        has_tables: bool = False,
        table_data: Optional[list] = None,
    ):
        self.page_number = page_number
        self.text = text
        self.image_bytes = image_bytes
        self.has_tables = has_tables
        self.table_data = table_data


class ParsedDocument:
    """Result of parsing an entire document."""

    def __init__(self, pages: list[ParsedPage], metadata: dict = None):
        self.pages = pages
        self.metadata = metadata or {}


class DocumentParser:
    """Unified document parser for PDFs, images, and text files."""

    MIN_TEXT_LENGTH = 30  # Minimum chars per page to consider it "has text"
    OCR_DPI = 300

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4)

    def parse(self, file_data: bytes, mime_type: str, filename: str) -> ParsedDocument:
        """Parse a document based on its MIME type."""
        logger.info(f"Parsing document: {filename} (type: {mime_type})")

        if mime_type == "application/pdf":
            return self._parse_pdf(file_data, filename)
        elif mime_type.startswith("image/"):
            return self._parse_image(file_data, filename)
        elif mime_type.startswith("text/"):
            return self._parse_text(file_data, filename)
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")

    def _parse_pdf(self, file_data: bytes, filename: str) -> ParsedDocument:
        """Parse a PDF - handles both digital and scanned PDFs."""
        pages = []
        metadata = {}

        # Extract metadata with PyMuPDF
        try:
            doc = fitz.open(stream=file_data, filetype="pdf")
            metadata = dict(doc.metadata) if doc.metadata else {}
            doc.close()
        except Exception as e:
            logger.warning(f"Could not extract PDF metadata: {e}")

        # Extract text and tables with pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF has {total_pages} pages")

                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    text = ""
                    has_tables = False
                    table_data = None

                    # Try to extract text directly (works for born-digital PDFs)
                    try:
                        extracted = page.extract_text() or ""
                        text = extracted.strip()
                    except Exception as e:
                        logger.warning(f"Text extraction failed on page {page_num}: {e}")

                    # Extract tables
                    try:
                        tables = page.extract_tables()
                        if tables:
                            has_tables = True
                            table_data = []
                            for table in tables:
                                # Convert table to markdown format
                                md_table = self._table_to_markdown(table)
                                table_data.append(table)
                                if md_table:
                                    text += f"\n\n{md_table}"
                    except Exception as e:
                        logger.warning(f"Table extraction failed on page {page_num}: {e}")

                    # If text is too short, try OCR
                    if len(text) < self.MIN_TEXT_LENGTH:
                        logger.info(f"Page {page_num}: Low text content ({len(text)} chars), attempting OCR")
                        ocr_text = self._ocr_pdf_page(file_data, page_num - 1)
                        if ocr_text and len(ocr_text) > len(text):
                            text = ocr_text

                    # Render page image
                    image_bytes = self._render_pdf_page(file_data, page_num - 1)

                    pages.append(ParsedPage(
                        page_number=page_num,
                        text=text,
                        image_bytes=image_bytes,
                        has_tables=has_tables,
                        table_data=table_data,
                    ))

        except Exception as e:
            logger.error(f"PDF parsing failed: {e}")
            raise ValueError(f"Failed to parse PDF: {str(e)}")

        metadata["page_count"] = len(pages)
        return ParsedDocument(pages=pages, metadata=metadata)

    def _ocr_pdf_page(self, pdf_data: bytes, page_index: int) -> str:
        """OCR a single PDF page using pytesseract."""
        try:
            # Render page to image using PyMuPDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            page = doc[page_index]
            # Render at higher DPI for better OCR
            mat = fitz.Matrix(self.OCR_DPI / 72, self.OCR_DPI / 72)
            pixmap = page.get_pixmap(matrix=mat)
            img_data = pixmap.tobytes("png")
            doc.close()

            # OCR with pytesseract
            image = Image.open(io.BytesIO(img_data))

            # Preprocessing for better OCR
            image = self._preprocess_for_ocr(image)

            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()

        except Exception as e:
            logger.warning(f"OCR failed for page {page_index + 1}: {e}")
            return ""

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR accuracy."""
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')

        # Simple threshold for binarization
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0, '1')

        return image

    def _render_pdf_page(self, pdf_data: bytes, page_index: int) -> Optional[bytes]:
        """Render a PDF page as a PNG image."""
        try:
            # Use PyMuPDF for rendering (more reliable across platforms)
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            page = doc[page_index]
            # Render at 150 DPI for thumbnails
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pixmap = page.get_pixmap(matrix=mat)
            img_data = pixmap.tobytes("png")
            doc.close()
            return img_data
        except Exception as e:
            logger.warning(f"Page rendering failed for page {page_index + 1}: {e}")
            return None

    def _parse_image(self, file_data: bytes, filename: str) -> ParsedDocument:
        """Parse an image file using OCR."""
        try:
            image = Image.open(io.BytesIO(file_data))

            # Preprocess
            processed = self._preprocess_for_ocr(image.copy())

            # OCR
            text = pytesseract.image_to_string(processed, lang='eng').strip()

            # Use original image as page image
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            image_bytes = img_buffer.getvalue()

            page = ParsedPage(
                page_number=1,
                text=text,
                image_bytes=image_bytes,
            )

            return ParsedDocument(
                pages=[page],
                metadata={"format": image.format, "size": image.size},
            )

        except Exception as e:
            logger.error(f"Image parsing failed: {e}")
            raise ValueError(f"Failed to parse image: {str(e)}")

    def _parse_text(self, file_data: bytes, filename: str) -> ParsedDocument:
        """Parse a plain text file."""
        try:
            # Try UTF-8, fall back to latin-1
            try:
                text = file_data.decode('utf-8')
            except UnicodeDecodeError:
                text = file_data.decode('latin-1')

            # Split into pages (every ~3000 chars or at natural breaks)
            pages = []
            chunk_size = 3000
            lines = text.split('\n')
            current_chunk = []
            current_length = 0
            page_num = 1

            for line in lines:
                current_chunk.append(line)
                current_length += len(line) + 1

                if current_length >= chunk_size:
                    page_text = '\n'.join(current_chunk)
                    # Create an image representation of the text
                    image_bytes = self._text_to_image(page_text, page_num)
                    pages.append(ParsedPage(
                        page_number=page_num,
                        text=page_text,
                        image_bytes=image_bytes,
                    ))
                    current_chunk = []
                    current_length = 0
                    page_num += 1

            # Don't forget the last chunk
            if current_chunk:
                page_text = '\n'.join(current_chunk)
                image_bytes = self._text_to_image(page_text, page_num)
                pages.append(ParsedPage(
                    page_number=page_num,
                    text=page_text,
                    image_bytes=image_bytes,
                ))

            if not pages:
                pages.append(ParsedPage(page_number=1, text="", image_bytes=self._text_to_image("(empty file)", 1)))

            return ParsedDocument(pages=pages, metadata={"format": "text"})

        except Exception as e:
            logger.error(f"Text parsing failed: {e}")
            raise ValueError(f"Failed to parse text file: {str(e)}")

    def _text_to_image(self, text: str, page_num: int) -> bytes:
        """Render text content as an image (for text files that have no page image)."""
        width, height = 800, 1100
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Use a basic font
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Draw text with word wrapping
        margin = 40
        y = margin
        max_width = width - 2 * margin

        for line in text.split('\n'):
            if y > height - margin:
                break
            # Simple word wrap
            words = line.split(' ')
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        draw.text((margin, y), current_line, fill='black', font=font)
                        y += 20
                    current_line = word
            if current_line:
                draw.text((margin, y), current_line, fill='black', font=font)
                y += 20

        # Page number
        draw.text((width - 60, height - 30), f"Page {page_num}", fill='gray', font=font)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def _table_to_markdown(self, table: list) -> str:
        """Convert a pdfplumber table to markdown format."""
        if not table or not table[0]:
            return ""

        rows = []
        for row in table:
            cells = [str(cell).replace("|", "\\|").strip() if cell else "" for cell in row]
            rows.append("| " + " | ".join(cells) + " |")

        if len(rows) < 1:
            return ""

        # Add header separator after first row
        header_sep = "| " + " | ".join(["---"] * len(table[0])) + " |"
        rows.insert(1, header_sep)

        return "\n".join(rows)


# Singleton
parser = DocumentParser()
