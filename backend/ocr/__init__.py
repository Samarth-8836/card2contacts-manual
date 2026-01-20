"""
OCR abstraction layer for Card2Contacts Enterprise

This module provides a clean abstraction for OCR services, allowing easy
switching between providers (Mistral, Fallback) from a single configuration point.

Usage:
    from backend.ocr import initialize_ocr_service, get_ocr_service

    # Initialize at startup
    initialize_ocr_service("mistral", {"api_key": "...", "model": "pixtral-12b-2409"})

    # Use anywhere in the application
    ocr_service = get_ocr_service()
    result = await ocr_service.extract_async(image_bytes)
    print(result.full_text)
"""

from backend.ocr.base import BaseOCRProvider, OCRResult
from backend.ocr.config import get_ocr_service, initialize_ocr_service, switch_ocr_provider
from backend.ocr.factory import OCRProviderFactory

__all__ = [
    'BaseOCRProvider',
    'OCRResult',
    'get_ocr_service',
    'initialize_ocr_service',
    'switch_ocr_provider',
    'OCRProviderFactory'
]
