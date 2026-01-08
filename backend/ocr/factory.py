from typing import Optional
from backend.ocr.base import BaseOCRProvider
from backend.ocr.providers.mistral_ocr import MistralOCRProvider
from backend.ocr.providers.fallback_ocr import FallbackOCRProvider


class OCRProviderFactory:
    """
    Factory for creating OCR provider instances
    Implements singleton pattern for provider reuse
    """

    _instances = {}

    @classmethod
    def create_provider(cls, provider_name: str, config: dict) -> BaseOCRProvider:
        """
        Create or retrieve OCR provider instance

        Args:
            provider_name: Name of provider ("mistral", "fallback")
            config: Provider-specific configuration

        Returns:
            BaseOCRProvider instance
        """
        # Use singleton pattern - one instance per provider type
        if provider_name not in cls._instances:
            cls._instances[provider_name] = cls._instantiate_provider(provider_name, config)

        return cls._instances[provider_name]

    @classmethod
    def _instantiate_provider(cls, provider_name: str, config: dict) -> BaseOCRProvider:
        """Instantiate specific provider"""
        provider_map = {
            "mistral": MistralOCRProvider,
            "fallback": FallbackOCRProvider
        }

        provider_class = provider_map.get(provider_name.lower())

        if not provider_class:
            print(f"⚠️  Unknown OCR provider '{provider_name}', falling back to FallbackOCRProvider")
            return FallbackOCRProvider(config)

        try:
            return provider_class(config)
        except Exception as e:
            print(f"❌ Failed to initialize {provider_name} OCR: {e}")
            print("⚠️  Falling back to FallbackOCRProvider")
            return FallbackOCRProvider(config)

    @classmethod
    def clear_instances(cls):
        """Clear cached instances (useful for testing)"""
        cls._instances = {}
