"""Exception hierarchy for Gemini extraction failures."""


class GeminiExtractionError(Exception):
    """Base exception for all Gemini extraction errors."""

    pass


class ExtractionAuthError(GeminiExtractionError):
    """Raised when the Gemini API key is missing or invalid."""

    pass


class ExtractionTimeoutError(GeminiExtractionError):
    """Raised when the Gemini API times out or rate limits unexpectedly."""

    pass


class ExtractionParseError(GeminiExtractionError):
    """Raised when Gemini returns malformed output that cannot be parsed into the schema."""

    pass
