"""Document domain models representing the ingestion and analysis results."""

from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentKind(StrEnum):
    """Broad classification of the document's content type."""

    TEXT_PDF = "TEXT_PDF"
    SCANNED_PDF = "SCANNED_PDF"
    MIXED_PDF = "MIXED_PDF"
    IMAGE = "IMAGE"


class PageAnalysis(BaseModel):
    """Analysis of a single document page."""

    page_number: int = Field(gt=0, description="1-indexed page number")
    has_text: bool = Field(description="Whether the page contains meaningful text")
    text_character_count: int = Field(ge=0, description="Length of extracted text")
    has_images: bool = Field(description="Whether the page contains images")
    page_kind: DocumentKind = Field(description="Classification of this specific page")


class DocumentMetadata(BaseModel):
    """Metadata describing the ingested document."""

    document_id: str = Field(description="Deterministic SHA-256 hash of document bytes")
    original_filename: str = Field(description="Original uploaded filename")
    file_extension: str = Field(description="File extension without dot (e.g. 'pdf')")
    size_bytes: int = Field(ge=0, description="Size of the document in bytes")
    page_count: int = Field(ge=1, description="Total number of pages")
    document_kind: DocumentKind = Field(description="Overall document classification")

    text_page_count: int = Field(default=0, ge=0, description="Number of text-based pages")
    image_page_count: int = Field(default=0, ge=0, description="Number of image-based pages")
    mixed_page_count: int = Field(default=0, ge=0, description="Number of mixed pages")
    empty_page_count: int = Field(default=0, ge=0, description="Number of empty pages")


class IngestedDocument(BaseModel):
    """Clean typed representation of a successfully ingested document."""

    metadata: DocumentMetadata = Field(description="Extracted metadata")
    file_path: str = Field(description="Safe internal path to the document file")
    page_analysis: list[PageAnalysis] = Field(
        default_factory=list, description="Analysis for each page"
    )
