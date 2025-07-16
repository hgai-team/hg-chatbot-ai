
from typing import Optional, List, Any, Dict
from openai import AsyncOpenAI


from llama_index.core.llms import ChatMessage

class XAILLM:
    """Service for generating text completions using LlamaIndex's integration with various LLM providers"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the LlamaIndex LLM service.

        Args:
            model_name: Name of the language model to use
            api_key: Authentication API key for the model provider
            base_url: Base URL for the model provider API

        Raises:
            ValueError: If either api_key or model_name is not provided
        """

        if api_key is None or model_name is None:
            raise ValueError("Either api_key and model_name must be provided.")

        self.model_name = model_name
        self.base_url = base_url or "https://api.x.ai/v1"
        self.llm = AsyncOpenAI(api_key=api_key, base_url=self.base_url)

    async def arun(
        self,
        messages: List[ChatMessage],
        **kwargs: Any
    ) -> str:
        """(Async) Generate a complete text response for the given messages

        Args:
            messages: List of ChatMessage objects representing the conversation
            **kwargs: Additional parameters to pass to the underlying LLM API

        Returns:
            Complete text response from the language model
        """
        serialized: List[Dict[str, Any]] = []
        for msg in messages:
            serialized.append({
                "role": msg.role,
                "content": [
                    {
                        "type": "text",
                        "text": msg.content
                    }
                ]
            })

        response = await self.llm.chat.completions.create(
            messages=serialized,
            model=self.model_name,
            **kwargs
        )

        return response
