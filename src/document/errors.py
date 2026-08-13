"""Exception hierarchy for document ingestion failures."""


class DocumentIngestionError(Exception):
    """Base exception for all document ingestion errors."""

    pass


class UnsupportedFileTypeError(DocumentIngestionError):
    """Raised when the file extension or type is not supported."""

    pass


class EmptyDocumentError(DocumentIngestionError):
    """Raised when a file has zero bytes or contains no pages."""

    pass


class DocumentTooLargeError(DocumentIngestionError):
    """Raised when a file exceeds the maximum allowed size."""

    pass


class CorruptDocumentError(DocumentIngestionError):
    """Raised when PyMuPDF or the system fails to open/read a PDF."""

    pass


class InvalidImageError(DocumentIngestionError):
    """Raised when an image file is corrupt or invalid."""

    pass
