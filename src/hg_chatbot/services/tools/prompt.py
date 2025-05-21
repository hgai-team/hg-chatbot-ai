import os
import yaml

from typing import Dict, Any, Optional, List

from llama_index.core.llms import ChatMessage, MessageRole

from core.config import get_core_settings

DEFAULT_SYSTEM_PROMPT = "Bạn là một hệ thống trợ lý hữu ích, chuyên nghiệp."

def prepare_chat_messages(
    prompt: Optional[str] = None,
    history: Optional[List[ChatMessage]] = None,
    system_prompt: Optional[str] = None,
    default_system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT
) -> List[ChatMessage]:
    """
    Chuẩn bị danh sách tin nhắn cho mô hình LLM.
    Nếu prompt là None, chỉ chuẩn bị system prompt và history.
    """
    messages: List[ChatMessage] = []
    _history = history or []

    has_system_in_history = any(msg.role == MessageRole.SYSTEM for msg in _history)
    effective_system_prompt_content: Optional[str] = None
    add_new_system_prompt = False

    if system_prompt is not None:
        # Ưu tiên system_prompt được cung cấp tường minh
        effective_system_prompt_content = system_prompt
        add_new_system_prompt = True
        # Nếu system prompt mới này giống hệt cái đầu tiên trong history, không cần thêm lại
        if _history and _history[0].role == MessageRole.SYSTEM and _history[0].content == system_prompt:
            add_new_system_prompt = False
    elif default_system_prompt is not None and not has_system_in_history:
        # Nếu không có system_prompt cụ thể, dùng default (nếu có) và history chưa có system msg
        effective_system_prompt_content = default_system_prompt
        add_new_system_prompt = True

    # Thêm system prompt mới vào đầu nếu cần
    if add_new_system_prompt and effective_system_prompt_content is not None:
        messages.append(ChatMessage(role=MessageRole.SYSTEM, content=effective_system_prompt_content))

    # Thêm lịch sử trò chuyện (loại bỏ system prompt cũ nếu đã thêm cái mới)
    history_to_add = _history
    if add_new_system_prompt and has_system_in_history and _history[0].role == MessageRole.SYSTEM:
         history_to_add = _history[1:]
    messages.extend(history_to_add)

    if prompt is not None:
        messages.append(ChatMessage(role=MessageRole.USER, content=prompt))

    return messages

def load_prompt(path: str, base_dir: str = None) -> Dict[str, Any]:
    """Loads YAML prompt data from a specified path."""
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

def get_prompt_path():
    pass

def apply_chat_template(template: str, **kwargs: Any) -> str:
    """Applies keyword arguments to a format string template."""
    if not template or 'template' not in template:
        return "Error: Invalid template data or missing 'template' key"
    try:
        return template['template'].format(**kwargs)
    except KeyError as e:
        return f"Error: Missing template key {e}"
    except Exception as e:
        return f"Error applying template: {e}"


