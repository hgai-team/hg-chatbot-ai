from typing import List

from core.config import get_core_settings
from .schema import ProcessedQueryInfo, RetrievedContext
from llama_index.core.llms import ChatMessage, MessageRole

class PromptFormattingService:
    def __init__(self, settings: get_core_settings):
         self.settings = settings

    def format_chat_prompt(
        self,
        processed_info: ProcessedQueryInfo,
        retrieved_context: RetrievedContext,
    ) -> List[ChatMessage]:
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=processed_info.system_prompt)]
        messages.extend(processed_info.history_messages)
        context_str = retrieved_context.context_string
        user_content = (
            f"Câu hỏi của người dùng: {processed_info.original_query}\n\n"
            f"CONTEXT:\n\n{context_str}\n\n"
            f"INSTRUCTIONS:\n\n{processed_info.instructions}"
        )
        messages.append(ChatMessage(role=MessageRole.USER, content=user_content))
        return messages

