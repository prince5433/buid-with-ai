import logging
import json
from config import settings
import google.generativeai as genai
from openai import OpenAI

logger = logging.getLogger(__name__)

class LLMProvider:
    """Unified LLM Provider with Primary (OpenAI) and Fallback (Gemini)."""
    
    def __init__(self):
        self._openai_client = None
        self._gemini_configured = False
        
        # Configure OpenAI
        if hasattr(settings, "openai_api_key") and settings.openai_api_key:
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI client initialized.")
            
        # Configure Gemini
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self._gemini_configured = True
            logger.info("Gemini client initialized.")

    def generate_content(self, prompt: str, system_instruction: str = None, temperature: float = 0.3, max_tokens: int = 2048) -> str:
        """Generate text using primary, falling back to secondary on failure."""
        
        # Try OpenAI First
        if self._openai_client:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                response = self._openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"OpenAI generation failed: {e}. Falling back to Gemini.")
        
        # Fallback to Gemini
        if self._gemini_configured:
            try:
                model = genai.GenerativeModel(
                    settings.llm_model,
                    system_instruction=system_instruction,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                return response.text.strip()
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}")
                raise e
                
        raise Exception("No LLM provider available.")

    def generate_json(self, prompt: str, system_instruction: str = None) -> dict:
        """Generate JSON structured output using primary, falling back to secondary."""
        
        # Try OpenAI First
        if self._openai_client:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                # OpenAI requires the prompt to mention JSON
                if "json" not in prompt.lower() and "json" not in system_instruction.lower():
                    prompt += "\nOutput in JSON format."
                    
                messages.append({"role": "user", "content": prompt})
                
                response = self._openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={ "type": "json_object" },
                    temperature=0.0,
                )
                content = response.choices[0].message.content.strip()
                return json.loads(content)
            except Exception as e:
                logger.warning(f"OpenAI JSON generation failed: {e}. Falling back to Gemini.")

        # Fallback to Gemini
        if self._gemini_configured:
            try:
                model = genai.GenerativeModel(
                    settings.llm_model,
                    system_instruction=system_instruction,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                return json.loads(response.text)
            except Exception as e:
                logger.error(f"Gemini JSON generation failed: {e}")
                raise e
                
        raise Exception("No LLM provider available.")

# Singleton
llm_provider = LLMProvider()
