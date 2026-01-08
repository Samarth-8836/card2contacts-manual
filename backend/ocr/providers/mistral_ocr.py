import base64
from typing import Optional
import sys
import os
from mistralai import Mistral

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.ocr.base import BaseOCRProvider, OCRResult


class MistralOCRProvider(BaseOCRProvider):
    """
    Mistral OCR implementation using official Mistral Python SDK

    Uses Mistral's official SDK to access OCR capabilities through the OCR API.
    Supports mistral-ocr-2512 and other OCR-specific models.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "mistral-ocr-2512")
        self.timeout = config.get("timeout", 60)

        if not self.api_key:
            print("⚠️  Warning: Mistral API key not provided. OCR extraction will fail silently.")
            self.client = None
        else:
            # Initialize official Mistral client
            self.client = Mistral(api_key=self.api_key)

    async def extract_async(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """Async Mistral OCR extraction using official SDK"""
        print(f"\n{'='*60}")
        print(f"[MISTRAL OCR ASYNC] Starting extraction for: {filename}")
        print(f"[MISTRAL OCR ASYNC] Image size: {len(image_bytes)} bytes")
        print(f"[MISTRAL OCR ASYNC] Model: {self.model}")

        try:
            if not self.client or not self.api_key or self.api_key == "your-mistral-key-here":
                print(f"[MISTRAL OCR ASYNC] ⚠️  No valid API key - returning empty result")
                return OCRResult(full_text="", provider="mistral_no_key")

            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{base64_image}"
            print(f"[MISTRAL OCR ASYNC] Base64 encoded length: {len(base64_image)} chars")

            print(f"[MISTRAL OCR ASYNC] Sending request to Mistral OCR API using official SDK...")

            # Use official Mistral SDK for OCR with correct document structure
            response = await self.client.ocr.process_async(
                model=self.model,
                document={
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            )

            print(f"[MISTRAL OCR ASYNC] ✅ Received response from Mistral SDK")
            print(f"[MISTRAL OCR ASYNC] Response type: {type(response)}")
            print(f"[MISTRAL OCR ASYNC] Number of pages: {len(response.pages) if hasattr(response, 'pages') else 'N/A'}")

            # Extract text from SDK response - OCRResponse has pages with markdown
            extracted_text = ""
            if hasattr(response, 'pages') and response.pages:
                # Concatenate markdown from all pages
                page_texts = []
                for page in response.pages:
                    if hasattr(page, 'markdown') and page.markdown:
                        page_texts.append(page.markdown)
                extracted_text = "\n\n".join(page_texts)
                print(f"[MISTRAL OCR ASYNC] ✅ Extracted text from {len(page_texts)} pages")
            else:
                print(f"[MISTRAL OCR ASYNC] ❌ No pages found in response!")
                print(f"[MISTRAL OCR ASYNC] Response attributes: {dir(response)}")

            final_text = extracted_text.strip() if extracted_text else ""
            print(f"[MISTRAL OCR ASYNC] Extracted text ({len(final_text)} chars): {final_text[:200]}...")
            print(f"{'='*60}\n")

            return OCRResult(
                full_text=final_text,
                confidence=None,
                details=[],
                provider="mistral_sdk"
            )

        except Exception as e:
            print(f"[MISTRAL OCR ASYNC] ❌ Exception: {type(e).__name__}: {e}")
            import traceback
            print(f"[MISTRAL OCR ASYNC] Traceback: {traceback.format_exc()}")
            print(f"{'='*60}\n")
            return OCRResult(full_text="", provider="mistral_error")

    def extract_sync(self, image_bytes: bytes, filename: str = "image.jpg") -> OCRResult:
        """Sync Mistral OCR extraction for bulk processing using official SDK"""
        print(f"\n{'='*60}")
        print(f"[MISTRAL OCR SYNC] Starting extraction for: {filename}")
        print(f"[MISTRAL OCR SYNC] Image size: {len(image_bytes)} bytes")
        print(f"[MISTRAL OCR SYNC] Model: {self.model}")

        try:
            if not self.client or not self.api_key or self.api_key == "your-mistral-key-here":
                print(f"[MISTRAL OCR SYNC] ⚠️  No valid API key - returning empty result")
                return OCRResult(full_text="", provider="mistral_no_key")

            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{base64_image}"
            print(f"[MISTRAL OCR SYNC] Base64 encoded length: {len(base64_image)} chars")

            print(f"[MISTRAL OCR SYNC] Sending request to Mistral OCR API using official SDK...")

            # Use official Mistral SDK for OCR with correct document structure
            response = self.client.ocr.process(
                model=self.model,
                document={
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            )

            print(f"[MISTRAL OCR SYNC] ✅ Received response from Mistral SDK")
            print(f"[MISTRAL OCR SYNC] Response type: {type(response)}")
            print(f"[MISTRAL OCR SYNC] Number of pages: {len(response.pages) if hasattr(response, 'pages') else 'N/A'}")

            # Extract text from SDK response - OCRResponse has pages with markdown
            extracted_text = ""
            if hasattr(response, 'pages') and response.pages:
                # Concatenate markdown from all pages
                page_texts = []
                for page in response.pages:
                    if hasattr(page, 'markdown') and page.markdown:
                        page_texts.append(page.markdown)
                extracted_text = "\n\n".join(page_texts)
                print(f"[MISTRAL OCR SYNC] ✅ Extracted text from {len(page_texts)} pages")
            else:
                print(f"[MISTRAL OCR SYNC] ❌ No pages found in response!")
                print(f"[MISTRAL OCR SYNC] Response attributes: {dir(response)}")

            final_text = extracted_text.strip() if extracted_text else ""
            print(f"[MISTRAL OCR SYNC] Extracted text ({len(final_text)} chars): {final_text[:200]}...")
            print(f"{'='*60}\n")

            return OCRResult(
                full_text=final_text,
                confidence=None,
                details=[],
                provider="mistral_sdk"
            )

        except Exception as e:
            print(f"[MISTRAL OCR SYNC] ❌ Exception: {type(e).__name__}: {e}")
            import traceback
            print(f"[MISTRAL OCR SYNC] Traceback: {traceback.format_exc()}")
            print(f"{'='*60}\n")
            return OCRResult(full_text="", provider="mistral_error")

    def health_check(self) -> bool:
        """Check Mistral API availability using official SDK"""
        try:
            if not self.client or not self.api_key or self.api_key == "your-mistral-key-here":
                return False

            # Use SDK to list models as health check
            models = self.client.models.list()
            return models is not None
        except:
            return False
