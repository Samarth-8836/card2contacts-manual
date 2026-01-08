from typing import Optional
from backend.ocr.base import BaseOCRProvider
from backend.ocr.factory import OCRProviderFactory


# Global OCR service instance
_global_ocr_service: Optional[BaseOCRProvider] = None


def initialize_ocr_service(provider_name: str, config: dict) -> BaseOCRProvider:
    """
    Initialize global OCR service

    Args:
        provider_name: Provider to use ("mistral", "fallback")
        config: Provider configuration dictionary

    Returns:
        Initialized OCR provider instance
    """
    global _global_ocr_service
    _global_ocr_service = OCRProviderFactory.create_provider(provider_name, config)
    return _global_ocr_service


def get_ocr_service() -> BaseOCRProvider:
    """
    Get the global OCR service instance

    Returns:
        Current OCR provider

    Raises:
        RuntimeError: If OCR service not initialized
    """
    if _global_ocr_service is None:
        raise RuntimeError("OCR service not initialized. Call initialize_ocr_service() first.")
    return _global_ocr_service


def switch_ocr_provider(provider_name: str, config: dict) -> BaseOCRProvider:
    """
    Switch to a different OCR provider at runtime

    Args:
        provider_name: New provider name
        config: New provider configuration

    Returns:
        New OCR provider instance
    """
    return initialize_ocr_service(provider_name, config)
