import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.ocr.base import BaseOCRProvider, OCRResult


class FallbackOCRProvider(BaseOCRProvider):
    """
    Fallback OCR provider that returns empty results
    Used when no OCR service is configured or available
    """

    async def extract_async(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """Return empty OCR result (async)"""
        return OCRResult(full_text="", provider="fallback")

    def extract_sync(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """Return empty OCR result (sync)"""
        return OCRResult(full_text="", provider="fallback")

    def health_check(self) -> bool:
        """Fallback provider is always healthy"""
        return True
