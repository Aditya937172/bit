from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google import genai


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CURRENT_DIR, ".env"))


class GeminiImageClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing in agent/.env")
        self.client = genai.Client(api_key=self.api_key)

    def generate_report_visual(self, prompt: str, output_path: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt],
        )
        saved_files = []
        text_parts = []
        for idx, part in enumerate(response.parts):
            if getattr(part, "text", None) is not None:
                text_parts.append(part.text)
            elif getattr(part, "inline_data", None) is not None:
                image = part.as_image()
                target_path = output_path
                if idx:
                    stem, ext = os.path.splitext(output_path)
                    target_path = f"{stem}_{idx}{ext or '.png'}"
                image.save(target_path)
                saved_files.append(target_path)
        return {
            "model": self.model,
            "saved_files": saved_files,
            "text_notes": text_parts,
        }
