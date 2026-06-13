"""
Document Classifier Service.

Uses Google Gemini to classify documents across multiple dimensions.
"""

import json
import logging
from typing import Optional
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """You are a document classifier. Analyze the following document content and classify it.

DOCUMENT FILENAME: {filename}
DOCUMENT CONTENT (first pages):
---
{content}
---

Classify this document and respond with ONLY valid JSON matching this exact schema:

{{
  "document_type": "<one of: report, invoice, letter, form, academic_paper, legal, manual, memo, resume, presentation, other>",
  "topic": "<one of: finance, healthcare, technology, legal, education, science, business, government, engineering, environment, other>",
  "content_characteristics": {{
    "has_tables": <true/false>,
    "has_images": <true/false>,
    "has_handwriting": <true/false>,
    "is_scanned": <true/false>,
    "has_charts": <true/false>,
    "language": "<ISO 639-1 code, e.g., en>",
    "page_count": <number>
  }},
  "sensitivity_level": "<one of: public, internal, confidential, restricted>",
  "summary": "<2-3 sentence summary of the document content>",
  "key_entities": ["<entity1>", "<entity2>", "...up to 10 entities"],
  "confidence_score": <0.0 to 1.0>
}}

IMPORTANT:
- Respond with ONLY the JSON object, no markdown formatting, no code blocks.
- If unsure about a field, make your best guess and reflect uncertainty in confidence_score.
- For sensitivity_level, consider if the content contains personal data, financial data, or proprietary information.
"""


class DocumentClassifier:
    """Classifies documents using Google Gemini."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        """Lazy-load the Gemini model."""
        if self._model is None:
            genai.configure(api_key=settings.gemini_api_key)
            self._model = genai.GenerativeModel(settings.llm_model)
        return self._model

    def classify(
        self, text_content: str, filename: str, page_count: int = 1, has_tables: bool = False
    ) -> dict:
        """
        Classify a document using LLM.

        Args:
            text_content: Extracted text from the document
            filename: Original filename
            page_count: Total number of pages
            has_tables: Whether tables were detected during parsing

        Returns:
            Classification result as a dictionary
        """
        # Truncate content to first ~4000 chars (enough context without hitting limits)
        truncated = text_content[:4000] if len(text_content) > 4000 else text_content

        if not truncated.strip():
            logger.warning(f"No text content for classification of {filename}")
            return self._fallback_classification(filename, page_count, has_tables)

        try:
            model = self._get_model()
            prompt = CLASSIFICATION_PROMPT.format(
                filename=filename,
                content=truncated,
            )

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                ),
            )

            # Parse JSON response
            result_text = response.text.strip()

            # Remove potential markdown code block wrappers
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                # Remove first and last line if they're code block markers
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                result_text = "\n".join(lines)

            result = json.loads(result_text)

            # Validate and fix page_count
            if "content_characteristics" in result:
                result["content_characteristics"]["page_count"] = page_count
                # Override table detection with actual parsing result
                if has_tables:
                    result["content_characteristics"]["has_tables"] = True

            logger.info(f"Classified {filename} as {result.get('document_type', 'unknown')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}")
            return self._fallback_classification(filename, page_count, has_tables)
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return self._fallback_classification(filename, page_count, has_tables)

    def _fallback_classification(
        self, filename: str, page_count: int, has_tables: bool
    ) -> dict:
        """Rule-based fallback classification when LLM is unavailable."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        name_lower = filename.lower()

        # Simple heuristic classification
        doc_type = "other"
        topic = "other"

        if ext == "pdf":
            doc_type = "report"
        elif ext in ("txt", "md"):
            doc_type = "memo"
        elif ext in ("jpg", "png", "jpeg", "tiff"):
            doc_type = "form"

        # Topic detection from filename
        topic_keywords = {
            "finance": ["invoice", "financial", "budget", "revenue", "expense", "accounting"],
            "legal": ["contract", "agreement", "legal", "law", "court", "compliance"],
            "technology": ["tech", "software", "code", "api", "system", "data"],
            "healthcare": ["medical", "health", "patient", "clinical", "diagnosis"],
            "education": ["syllabus", "course", "assignment", "exam", "grade"],
            "science": ["research", "study", "experiment", "analysis", "paper"],
            "business": ["memo", "meeting", "proposal", "report", "strategy"],
        }

        for t, keywords in topic_keywords.items():
            if any(kw in name_lower for kw in keywords):
                topic = t
                break

        return {
            "document_type": doc_type,
            "topic": topic,
            "content_characteristics": {
                "has_tables": has_tables,
                "has_images": ext in ("jpg", "png", "jpeg", "tiff", "bmp"),
                "has_handwriting": False,
                "is_scanned": False,
                "has_charts": False,
                "language": "en",
                "page_count": page_count,
            },
            "sensitivity_level": "internal",
            "summary": f"Document: {filename}",
            "key_entities": [],
            "confidence_score": 0.3,
        }


# Singleton
classifier = DocumentClassifier()
