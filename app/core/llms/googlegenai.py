from typing import Optional, Any, Generator
from llama_index.llms.google_genai import GoogleGenAI as LlamaGoogleGenAI
class GoogleGenAILLM:
    """Service for generating text completions using LlamaIndex's integration with Google Generative AI (Gemini)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize the Google Generative AI LLM service.

        Args:
            model_name: Name of the Gemini model to use (e.g., "gemini-pro")
            api_key: Authentication API key for Google Generative AI

        Raises:
            ValueError: If either api_key or model_name is not provided
        """

        if api_key is None or model_name is None:
            raise ValueError("Either api_key and model_name must be provided.")

        self.model_name = model_name
        self.llm = LlamaGoogleGenAI(model=model_name, api_key=api_key)

    def run(
        self,
        messages: str,
        **kwargs: Any
    ) -> str:
        """Generate a complete text response for the given messages

        Args:
            messages: List of message dictionaries representing the conversation
            **kwargs: Additional parameters to pass to the underlying LLM API

        Returns:
            Complete text response from the language model
        """
        response = self.llm.chat(messages=messages, **kwargs)
        return response.message.content

    async def arun(
        self,
        messages: Any,
        **kwargs: Any
    ) -> str:
        """Generate a complete text response for the given messages (asynchronously).

        Args:
            messages: A single string (user message) or a list of ChatMessage objects or dicts representing the conversation.
            **kwargs: Additional parameters to pass to the underlying LLM API (e.g., temperature).

        Returns:
            Complete text response from the language model.
        """
        response = await self.llm.achat(messages=messages, **kwargs)
        return response

    def stream(
        self,
        messages: str,
        **kwargs: Any
    ) -> Generator[str, None, None]:
        """
        Generate streaming text responses for the given messages.

        Args:
            messages: List of message dictionaries representing the conversation
            **kwargs: Additional parameters to pass to the underlying LLM API

        Returns:
            Generator yielding content chunks as they are received from the API
        """
        stream_response = self.llm.stream_chat(messages=messages, **kwargs)

        for chunk in stream_response:
            yield chunk.delta
