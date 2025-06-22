import os
import yaml

from typing import Dict, Any, Optional, List
from llama_index.core.llms import ChatMessage, MessageRole

from core.config import get_core_settings
from services.agentic_workflow.schema import ContextRetrieved, QueryProcessed

class PromptProcessorTool:
    DEFAULT_SYSTEM_PROMPT = "Bạn là một hệ thống trợ lý hữu ích, chuyên nghiệp."

    def __init__(self, settings: get_core_settings):
         self.settings = settings

    @classmethod
    def format_chat_prompt(
        cls,
        processed_info: QueryProcessed,
        retrieved_context: ContextRetrieved,
    ) -> List[ChatMessage]:
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=processed_info.system_prompt)]
        messages.extend(processed_info.history_messages)
        context_str = retrieved_context.context_string
        user_content = (
            f"INSTRUCTIONS:\n{processed_info.instructions}\n\n"
            f"Câu hỏi của người dùng:\n{processed_info.original_query}\n\n"
            f"CONTEXT:\n{context_str}"

        )
        messages.append(ChatMessage(role=MessageRole.USER, content=user_content))
        return messages

    @classmethod
    def prepare_chat_messages(
        cls,
        prompt: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
        default_system_prompt: Optional[str] = None
    ) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        _history = history or []

        has_system_in_history = any(msg.role == MessageRole.SYSTEM for msg in _history)
        effective_system_prompt_content: Optional[str] = None
        add_new_system_prompt = False

        if system_prompt is not None:
            effective_system_prompt_content = system_prompt
            add_new_system_prompt = True
            if _history and _history[0].role == MessageRole.SYSTEM and _history[0].content == system_prompt:
                add_new_system_prompt = False
        elif default_system_prompt is not None and not has_system_in_history:
            effective_system_prompt_content = default_system_prompt
            add_new_system_prompt = True
        elif default_system_prompt is None and not has_system_in_history:
            effective_system_prompt_content = cls.DEFAULT_SYSTEM_PROMPT
            add_new_system_prompt = True

        if add_new_system_prompt and effective_system_prompt_content is not None:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=effective_system_prompt_content))

        history_to_add = _history
        if add_new_system_prompt and has_system_in_history and _history[0].role == MessageRole.SYSTEM:
            history_to_add = _history[1:]
        messages.extend(history_to_add)

        if prompt is not None:
            messages.append(ChatMessage(role=MessageRole.USER, content=prompt))

        return messages

    @classmethod
    def load_prompt(
        cls,
        path: str,
        base_dir: str = None
    ) -> Dict[str, Any]:
        full_path = path
        if base_dir:
            full_path = os.path.join(base_dir, path)
        elif not os.path.isabs(path):
            full_path = os.path.join(os.getcwd(), path)

        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if not isinstance(data, dict):
                    return {}
                return data
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            return {}
        except Exception as e:
            return {}

    @classmethod
    def apply_chat_template(
        cls,
        template: str,
        **kwargs: Any
    ) -> str:
        if not template or 'template' not in template:
            return "Error: Invalid template data or missing 'template' key"
        try:
            return template['template'].format(**kwargs)
        except KeyError as e:
            return f"Error: Missing template key {e}"
        except Exception as e:
            return f"Error applying template: {e}"
