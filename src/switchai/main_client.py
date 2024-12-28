import glob
import importlib
import os
from typing import List, Optional, Union, Generator

from .base_client import BaseClient
from .types import ChatResponse, TextEmbeddingResponse, TranscriptionResponse, ImageGenerationResponse, ChatChoice


class SwitchAI(BaseClient):
    """
    The SwitchAI client class.

    Args:
            provider: The name of the provider to use.
            model_name: The name of the model to use.
            api_key: The API key to use, if not set it will be read from the environment variable. Defaults to None.
    """

    def __init__(self, provider: str, model_name: str, api_key: Optional[str] = None):
        self.provider = provider.lower()
        self.model_name = model_name

        self.client, self.model_category = self._get_provider_client(api_key)

    def _get_provider_client(self, api_key: Optional[str]) -> tuple[BaseClient, str]:
        # Get all provider files matching the pattern _*.py
        provider_files = glob.glob(os.path.join(os.path.dirname(__file__), "providers", "_*.py"))
        provider_modules = [os.path.basename(f)[1:-3] for f in provider_files]
        provider_modules.remove("_init__")

        # Check if the specified provider is supported
        if self.provider not in provider_modules:
            supported_providers = ", ".join(provider_modules)
            raise ValueError(
                f"Provider '{self.provider}' is not supported. Supported providers are: {supported_providers}."
            )

        # Import the provider module
        provider_module = importlib.import_module(f"switchai.providers._{self.provider}")

        model_supported = False
        model_category = None
        # Check if the model is supported by the specified provider and identify the category
        for category, models in provider_module.SUPPORTED_MODELS.items():
            if self.model_name in models:
                model_supported = True
                model_category = category
                break

        if not model_supported:
            # Find alternative providers that support the model
            alternative_providers = [
                provider
                for provider in provider_modules
                if any(
                    self.model_name in models
                    for models in importlib.import_module(f"switchai.providers._{provider}").SUPPORTED_MODELS.values()
                )
            ]

            if alternative_providers:
                alternatives = ", ".join(alternative_providers)
                raise ValueError(
                    f"Model '{self.model_name}' is not supported by provider '{self.provider}'. "
                    f"However, it is supported by: {alternatives}."
                )
            else:
                raise ValueError(f"Model '{self.model_name}' is not supported by any provider.")

        # Retrieve the API key from the environment if not provided
        if api_key is None:
            api_key = os.environ.get(provider_module.API_KEY_NAMING)
        if api_key is None:
            raise ValueError(
                f"The api_key client option must be set either by passing api_key to the client or by setting the {provider_module.API_KEY_NAMING} environment variable."
            )

        # Construct the client class name and get the class from the provider module
        class_name = f"{self.provider.capitalize()}ClientAdapter"
        client_class = getattr(provider_module, class_name)

        # Return an instance of the client class and the model category
        return client_class(self.model_name, api_key), model_category

    def chat(
            self,
            messages: List[str | ChatChoice | dict],
            temperature: Optional[float] = 1.0,
            max_tokens: Optional[int] = None,
            n: Optional[int] = 1,
            tools: Optional[List] = None,
            stream: Optional[bool] = False,
    ) -> Union[ChatResponse, Generator[ChatResponse, None, None]]:
        if self.model_category != "chat":
            raise ValueError(f"Model '{self.model_name}' is not a chat model.")
        return self.client.chat(messages, temperature, max_tokens, n, tools, stream)

    def embed(self, inputs: Union[str, List[str]]) -> TextEmbeddingResponse:
        if self.model_category != "embed":
            raise ValueError(f"Model '{self.model_name}' is not an embedding model.")
        return self.client.embed(inputs)

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResponse:
        if self.model_category != "transcribe":
            raise ValueError(f"Model '{self.model_name}' is not a speech-to-text model.")
        return self.client.transcribe(audio_path, language)

    def generate_image(self, prompt: str, n: int = 1) -> ImageGenerationResponse:
        if self.model_category != "generate_image":
            raise ValueError(f"Model '{self.model_name}' is not an image generation model.")
        return self.client.generate_image(prompt, n)