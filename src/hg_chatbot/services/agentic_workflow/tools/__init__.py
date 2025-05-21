from services import get_settings_cached

from .query_analyzer_agent import QueryAnalyzerAgent
from .evaluation_agent import EvaluationAgent

def get_query_analyzer_agent(
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.VAHACHA_AGENT_PROMPT_PATH

    return QueryAnalyzerAgent(
        agent_prompt_path=agent_prompt_path,
        prompt_template_path=settings.BASE_PROMPT_PATH
    )

def get_evaluation_agent(
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.VAHACHA_AGENT_PROMPT_PATH

    return EvaluationAgent(
        agent_prompt_path=agent_prompt_path,
        prompt_template_path=settings.BASE_PROMPT_PATH
    )
