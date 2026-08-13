"""Document Ingestion Service for validating and analyzing incoming files."""

import hashlib
import os
import shutil
import tempfile

import pymupdf

from src.config import settings
from src.document.errors import (
    CorruptDocumentError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidImageError,
    UnsupportedFileTypeError,
)
from src.document.models import (
    DocumentKind,
    DocumentMetadata,
    IngestedDocument,
    PageAnalysis,
)

SUPPORTED_PDF = {"pdf"}
SUPPORTED_IMAGE = {"png", "jpg", "jpeg"}
SUPPORTED_EXTENSIONS = SUPPORTED_PDF | SUPPORTED_IMAGE


class DocumentIngestionService:
    """Service to ingest, validate, and analyze Mechanical Datasheet documents."""

    def __init__(self, temp_dir: str | None = None):
        """Initialize the service.

        Args:
            temp_dir: Optional custom temporary directory for internal storage.
                      If None, the system default temp directory is used.
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()

    def ingest_file(self, file_path: str, original_filename: str) -> IngestedDocument:
        """Ingest a document from a file path.

        Validates size, extension, generates deterministic ID, analyzes content,
        and safely stores a copy in the internal temp directory.
        """
        # 1. Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 2. Validate Extension
        # Clean the filename to prevent traversal when extracting extension
        clean_filename = os.path.basename(original_filename)
        ext = clean_filename.split(".")[-1].lower() if "." in clean_filename else ""
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}"
            )

        # 3. Validate Size
        size_bytes = os.path.getsize(file_path)
        if size_bytes == 0:
            raise EmptyDocumentError("File is empty (0 bytes).")

        max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            raise DocumentTooLargeError(
                f"File exceeds maximum size of {settings.MAX_DOCUMENT_SIZE_MB}MB."
            )

        # 4. Generate deterministic Document ID (SHA-256)
        doc_id = self._compute_sha256(file_path)

        # 5. Route to specific analyzer
        try:
            if ext in SUPPORTED_PDF:
                page_count, doc_kind, pages = self._analyze_pdf(file_path)
            else:
                page_count, doc_kind, pages = self._analyze_image(file_path)
        except Exception as e:
            if ext in SUPPORTED_PDF:
                raise CorruptDocumentError(f"Cannot open PDF: {e}") from e
            else:
                raise InvalidImageError(f"Cannot open image: {e}") from e

        if page_count == 0:
            raise EmptyDocumentError("Document has 0 pages.")

        # 6. Prepare Metadata
        text_pages = sum(1 for p in pages if p.page_kind == DocumentKind.TEXT_PDF)
        image_pages = sum(1 for p in pages if p.page_kind == DocumentKind.SCANNED_PDF)
        mixed_pages = sum(1 for p in pages if p.page_kind == DocumentKind.MIXED_PDF)
        empty_pages = sum(1 for p in pages if not p.has_text and not p.has_images)

        metadata = DocumentMetadata(
            document_id=doc_id,
            original_filename=clean_filename,
            file_extension=ext,
            size_bytes=size_bytes,
            page_count=page_count,
            document_kind=doc_kind,
            text_page_count=text_pages,
            image_page_count=image_pages,
            mixed_page_count=mixed_pages,
            empty_page_count=empty_pages,
        )

        # 7. Safe internal copy
        safe_path = os.path.join(self.temp_dir, f"{doc_id}.{ext}")
        if file_path != safe_path:
            shutil.copy2(file_path, safe_path)

        return IngestedDocument(metadata=metadata, file_path=safe_path, page_analysis=pages)

    def _compute_sha256(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file deterministically."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _analyze_pdf(self, file_path: str) -> tuple[int, DocumentKind, list[PageAnalysis]]:
        """Analyze a PDF document to determine page count and classifications."""
        doc = pymupdf.open(file_path)

        pages = []
        for i, page in enumerate(doc):
            # Extract text
            text = page.get_text()
            text_len = len(text)
            alnum_count = sum(c.isalnum() for c in text)

            # Extract image count
            images = page.get_image_info()
            has_images = len(images) > 0

            # Page heuristics
            has_text = (
                text_len >= settings.MIN_MEANINGFUL_TEXT_CHARS
                and alnum_count >= settings.MIN_MEANINGFUL_ALPHANUMERIC_CHARS
            )

            if has_text and has_images:
                page_kind = DocumentKind.MIXED_PDF
            elif has_text:
                page_kind = DocumentKind.TEXT_PDF
            elif has_images:
                page_kind = DocumentKind.SCANNED_PDF
            else:
                # Empty page or stray marks
                page_kind = DocumentKind.IMAGE

            pages.append(
                PageAnalysis(
                    page_number=i + 1,
                    has_text=has_text,
                    text_character_count=text_len,
                    has_images=has_images,
                    page_kind=page_kind,
                )
            )

        page_count = len(doc)
        doc.close()

        # Document classification heuristic based on overall pages
        if page_count == 0:
            return 0, DocumentKind.IMAGE, []

        has_any_text = any(p.has_text for p in pages)
        has_any_images = any(p.has_images for p in pages)

        if has_any_text and has_any_images:
            # Check if it's mostly text with a few images vs truly mixed
            # For simplicity, if both exist meaningfully across the document, call it MIXED
            overall_kind = DocumentKind.MIXED_PDF
        elif has_any_text:
            overall_kind = DocumentKind.TEXT_PDF
        elif has_any_images:
            overall_kind = DocumentKind.SCANNED_PDF
        else:
            # Completely empty document, fallback to IMAGE for structural reasons
            overall_kind = DocumentKind.IMAGE

        return page_count, overall_kind, pages

    def _analyze_image(self, file_path: str) -> tuple[int, DocumentKind, list[PageAnalysis]]:
        """Analyze an Image to validate it can be opened safely."""
        # 1. Structural validation via magic bytes
        with open(file_path, "rb") as f:
            header = f.read(8)

        is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = header.startswith(b"\xff\xd8\xff")

        if not (is_png or is_jpeg):
            raise InvalidImageError("File does not have a valid PNG or JPEG signature.")

        # 2. Open to confirm it is readable
        try:
            doc = pymupdf.open(file_path)
            page_count = len(doc)
            doc.close()
        except Exception as e:
            raise InvalidImageError(f"Cannot open image: {e}") from e

        # Images are treated as a single page scanned document conceptually
        pages = [
            PageAnalysis(
                page_number=1,
                has_text=False,
                text_character_count=0,
                has_images=True,
                page_kind=DocumentKind.IMAGE,
            )
        ]
        return page_count, DocumentKind.IMAGE, pages
