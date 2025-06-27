import json

from typing import Optional, Any, AsyncGenerator, List
from llama_index.llms.openai import OpenAI as LlamaOpenAI

from llama_index.core.llms import ChatMessage

class OpenAILLM:
    """Service for generating text completions using LlamaIndex's integration with various LLM providers"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize the LlamaIndex LLM service.

        Args:
            model_name: Name of the language model to use
            api_key: Authentication API key for the model provider

        Raises:
            ValueError: If either api_key or model_name is not provided
        """

        if api_key is None or model_name is None:

            raise ValueError("Either api_key and model_name must be provided.")

        self.model_name = model_name
        self.llm = LlamaOpenAI(model=model_name, api_key=api_key)

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
        try:
            response = await self.llm.achat(messages=messages, **kwargs)

            # print('\narun openai==========================\n')
            # print(response.raw)
            # print('\narun openai==========================\n')

            return response.message.content
        except Exception as e:
            raise

    async def astream(
        self,
        messages: List[ChatMessage],
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        (Async) Generate streaming text responses for the given messages.

        Args:
            messages: List of ChatMessage objects representing the conversation
            **kwargs: Additional parameters to pass to the underlying LLM API

        Returns:
            AsyncGenerator yielding content chunks as they are received from the API
        """
        try:
            stream_response = await self.llm.astream_chat(messages=messages, **kwargs)

            async for chunk in stream_response:
                yield chunk.delta
        except Exception as e:
            pass


# hg_chatbot/core/llms/openai.py

# import asyncio
# from typing import Optional, Any, List, AsyncGenerator, Dict

# from openai import AsyncOpenAI, OpenAIError
# from llama_index.core.llms import ChatMessage as LlamaChatMessage

# from llama_index.core.llms import MessageRole

# class LLMError(Exception): pass

# class OpenAILLM:
#     """Service for generating text completions using the official OpenAI library"""

#     def __init__(
#         self,
#         api_key: Optional[str] = None,
#         model_name: Optional[str] = None,
#     ):
#         if not api_key or not model_name:
#             raise ValueError("Both api_key and model_name must be provided.")

#         self.model_name = model_name

#         self.openai_client = AsyncOpenAI(api_key=api_key)

#     def _convert_messages(self, messages: List[LlamaChatMessage]) -> List[Dict[str, str]]:
#         """Converts LlamaIndex ChatMessage list to OpenAI dict list."""
#         openai_messages = []
#         valid_roles = {'system', 'user', 'assistant', 'function', 'tool'}

#         for msg in messages:
#             role_attr = getattr(msg, 'role', MessageRole.USER)
#             content = getattr(msg, 'content', '')

#             role_str = ""

#             if isinstance(role_attr, MessageRole):
#                 role_str = role_attr.value
#             elif isinstance(role_attr, str):
#                 role_str = role_attr
#             else:
#                 role_str = str(role_attr)

#             role_str = role_str.lower()


#             if role_str not in valid_roles:
#                 role_str = 'user'

#             openai_messages.append({"role": role_str, "content": str(content)})

#         return openai_messages

#     async def arun(
#         self,
#         messages: List[LlamaChatMessage],
#         **kwargs: Any
#     ) -> str:
#         """Generate a complete text response for the given messages using openai library"""
#         if not messages: return ""
#         openai_messages = self._convert_messages(messages)
#         if not openai_messages: return ""

#         try:
#             response = await self.openai_client.chat.completions.create(
#                 model=self.model_name,
#                 messages=openai_messages,
#                 **kwargs
#             )
#             if response.choices and response.choices[0].message:
#                 content = response.choices[0].message.content
#                 return content if content is not None else ""
#             else:
#                 return ""
#         except OpenAIError as e:
#             raise LLMError(f"OpenAI API call failed in run: {e}") from e
#         except Exception as e:
#             raise LLMError(f"Unexpected error during OpenAI run call: {e}") from e

#     async def astream(
#         self,
#         messages: List[LlamaChatMessage],
#         **kwargs: Any
#     ) -> AsyncGenerator[str, None]:
#         """
#         Generate streaming text responses for the given messages using openai library.
#         """
#         if not messages:
#              if False: yield
#              return
#         openai_messages = self._convert_messages(messages)
#         if not openai_messages:
#              if False: yield
#              return

#         try:
#             stream = await self.openai_client.chat.completions.create(
#                 model=self.model_name,
#                 messages=openai_messages,
#                 stream=True,
#                 **kwargs
#             )
#             async for chunk in stream:
#                 if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
#                     yield chunk.choices[0].delta.content
#         except OpenAIError as e:
#             raise LLMError(f"OpenAI API call failed during stream: {e}") from e
#         except Exception as e:
#             raise LLMError(f"Unexpected error during OpenAI stream call: {e}") from e
