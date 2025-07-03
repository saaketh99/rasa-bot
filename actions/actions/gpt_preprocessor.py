from typing import Any, Dict, Text
from rasa.engine.graph import GraphComponent, ExecutionContext
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.constants import TEXT
from rasa.shared.nlu.training_data.message import Message
from rasa.engine.recipes.default_recipe import DefaultV1Recipe

from openai import OpenAI 
import logging

logger = logging.getLogger(__name__)

@DefaultV1Recipe.register(
    component_types=[GraphComponent], is_trainable=False
)
class DeepSeekPreprocessor(GraphComponent):
    def __init__(self, config: Dict[Text, Any]) -> None:
        self.config = config
        self.api_key = config.get("sk-e2a7c85c035e482ebe1639c9b6754ad5", "")
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        logger.debug(f"[DeepSeekPreprocessor] Initialized with config: {self.config}")

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "DeepSeekPreprocessor":
        return cls(config)

    def correct_text(self, text: str) -> str:
        logger.debug(f"[DeepSeekPreprocessor] Correcting text: '{text}'")
        prompt = (
            f"Correct the following sentence by:\n"
            f"- Fixing typos\n"
            f"- Translating Telugu to English\n"
            f"- Expanding known abbreviations like Hyd → Hyderabad, Vskp → Visakhapatnam.\n\n"
            f"Input: \"{text}\"\nCorrected:"
        )

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100,
            )
            corrected = response.choices[0].message.content.strip()
            logger.debug(f"[DeepSeekPreprocessor] Correction result: '{corrected}'")
            return corrected
        except Exception as e:
            logger.error(f"[DeepSeekPreprocessor] DeepSeek API Error: {e}")
            return text

    def process(self, message: Message) -> Message:
        original_text = message.get(TEXT)
        logger.debug(f"[DeepSeekPreprocessor] Original message text: '{original_text}'")

        corrected_text = self.correct_text(original_text)
        logger.debug(f"[DeepSeekPreprocessor] Corrected message text: '{corrected_text}'")

        message.set(TEXT, corrected_text)
        return message