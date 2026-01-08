from abc import ABC, abstractmethod
from typing import Dict, Optional, List


class OCRResult:
    """Standardized OCR result format"""

    def __init__(
        self,
        full_text: str,
        confidence: Optional[float] = None,
        details: Optional[List] = None,
        provider: str = "unknown"
    ):
        self.full_text = full_text
        self.confidence = confidence
        self.details = details or []
        self.provider = provider

    def to_dict(self) -> Dict:
        """Convert result to dictionary format"""
        return {
            "full_text": self.full_text,
            "confidence": self.confidence,
            "details": self.details,
            "provider": self.provider
        }


class BaseOCRProvider(ABC):
    """Abstract base class for all OCR providers"""

    def __init__(self, config: dict):
        """
        Initialize OCR provider with configuration

        Args:
            config: Dictionary containing provider-specific settings
        """
        self.config = config
        self.provider_name = self.__class__.__name__

    @abstractmethod
    async def extract_async(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """
        Async OCR extraction - for single scans

        Args:
            image_bytes: Raw image bytes
            filename: Optional filename for logging

        Returns:
            OCRResult object with extracted text
        """
        pass

    @abstractmethod
    def extract_sync(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """
        Sync OCR extraction - for bulk processing

        Args:
            image_bytes: Raw image bytes
            filename: Optional filename for logging

        Returns:
            OCRResult object with extracted text
        """
        pass

    def health_check(self) -> bool:
        """
        Check if OCR service is available

        Returns:
            True if service is healthy, False otherwise
        """
        return True

    def get_provider_info(self) -> Dict:
        """Get provider metadata"""
        # Filter out sensitive keys like API keys
        safe_config = {k: v for k, v in self.config.items() if "key" not in k.lower()}
        return {
            "name": self.provider_name,
            "config": safe_config
        }
