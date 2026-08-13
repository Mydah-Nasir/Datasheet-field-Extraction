"""Document layer — handling file ingestion, validation, and PyMuPDF analysis."""

from src.document.errors import (
    CorruptDocumentError,
    DocumentIngestionError,
    DocumentTooLargeError,
    EmptyDocumentError,
    InvalidImageError,
    UnsupportedFileTypeError,
)
from src.document.models import DocumentKind, DocumentMetadata, IngestedDocument, PageAnalysis
from src.document.service import DocumentIngestionService

__all__ = [
    "DocumentKind",
    "PageAnalysis",
    "DocumentMetadata",
    "IngestedDocument",
    "DocumentIngestionError",
    "UnsupportedFileTypeError",
    "EmptyDocumentError",
    "DocumentTooLargeError",
    "CorruptDocumentError",
    "InvalidImageError",
    "DocumentIngestionService",
]
