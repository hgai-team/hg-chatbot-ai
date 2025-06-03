from services import (
    get_settings_cached,
    get_langfuse_instrumentor_cached,
    get_google_genai_llm,
    get_openai_llm,
    get_mongodb_memory_store
)

from services.tools import (
    get_search_tool,
)

from services.agentic_workflow.tools import (
    get_query_analyzer_agent,
    get_evaluation_agent,
)

from .chat import ChatService
from .context_retriever import ContextRetrievalService
from .prompt_formatter import PromptFormattingService
from .query_processor import QueryProcessingService


def get_query_processing_service(
    database_name: str = None,
    collection_name: str = None,
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.VAHACHA_AGENT_PROMPT_PATH

    if database_name is None:
        database_name = settings.MONGODB_BASE_DATABASE_NAME
    elif not database_name.endswith(settings.MONGODB_BASE_DATABASE_NAME):
        database_name = f"{database_name}{settings.MONGODB_BASE_DATABASE_NAME}"

    if collection_name is None:
        collection_name = settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME
    elif not collection_name.endswith(settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME):
        collection_name = f"{collection_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL,
    )

    return QueryProcessingService(
        query_analyzer=get_query_analyzer_agent(
            agent_prompt_path=agent_prompt_path
        ),
        evaluation_agent=get_evaluation_agent(
            agent_prompt_path=agent_prompt_path
        ),
        memory_store=get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        ),
        settings=get_settings_cached(),
        llm_runner=google_llm.run,
        llm_arunner=google_llm.arun
    )


def get_context_retrieval_service(
    bot_name: str,
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.VAHACHA_AGENT_PROMPT_PATH

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING,
    )

    return ContextRetrievalService(
        search_tool=get_search_tool(
            bot_name=bot_name
        ),
        evaluation_agent=get_evaluation_agent(
            agent_prompt_path=agent_prompt_path
        ),
        llm_runner=google_llm.run,
        llm_arunner=google_llm.arun,
    )


def get_prompt_formatting_service():
    return PromptFormattingService(
        settings=get_settings_cached()
    )

def get_chat_service(
    bot_name: str,
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.VAHACHA_AGENT_PROMPT_PATH


    database_name = f"{bot_name}{settings.MONGODB_BASE_DATABASE_NAME}"
    collection_name = f"{bot_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"


    main_llm = get_openai_llm()

    return ChatService(
        query_processor=get_query_processing_service(
            database_name=database_name,
            collection_name=collection_name,
            agent_prompt_path=agent_prompt_path
        ),
        context_retriever=get_context_retrieval_service(
            bot_name=bot_name,
            agent_prompt_path=agent_prompt_path
        ),
        prompt_formatter=get_prompt_formatting_service(),
        evaluation_agent=get_evaluation_agent(
            agent_prompt_path=agent_prompt_path
        ),
        google_llm=get_google_genai_llm(
            model_name=get_settings_cached().GOOGLEAI_MODEL,
        ),
        main_llm=main_llm,
        memory_store=get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        ),
        instrumentor=get_langfuse_instrumentor_cached()
    )
