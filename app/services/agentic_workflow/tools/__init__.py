from services import (
    get_settings_cached,
    get_google_genai_llm,
    get_mongodb_memory_store,

    get_excel_reader_cached,
    get_pandas_excel_reader_cached,
    get_pymupdf_reader_cached,
    get_docx_reader_cached,
    get_markdown_reader_cached,

    get_openai_embedding_cached,
    get_mongodb_doc_store,
    get_qdrant_vector_store
)

from .context_retriever import ContextRetrievalTool
from .evaluation_agent import EvaluationAgentTool
from .files_processor import FileProcessorTool
from .prompt_processor import PromptProcessorTool
from .query_analyzer_agent import QueryAnalyzerAgentTool
from .query_processor import QueryProcessingTool
from .search import SearchTool

def get_context_retrieval_tool(
    bot_name: str,
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING,
    )

    return ContextRetrievalTool(
        search=get_search_tool(
            bot_name=bot_name
        ),
        eval_agent=get_evaluation_agent_tool(
            agent_prompt_path=agent_prompt_path
        ),
        llm_runner=google_llm.run,
        llm_arunner=google_llm.arun,
    )

def get_evaluation_agent_tool(
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

    return EvaluationAgentTool(
        agent_prompt_path=agent_prompt_path,
        prompt_template_path=settings.BASE_PROMPT_PATH
    )

def get_file_processor_tool(
    bot_name: str,
):
    return FileProcessorTool(bot_name=bot_name)

def get_prompt_processor_tool():
    return PromptProcessorTool(
        settings=get_settings_cached()
    )

def get_query_analyzer_agent_tool(
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

    return QueryAnalyzerAgentTool(
        agent_prompt_path=agent_prompt_path,
        prompt_template_path=settings.BASE_PROMPT_PATH
    )

def get_query_processing_tool(
    bot_name: str,
    database_name: str = None,
    collection_name: str = None,
    agent_prompt_path: str = None,
):
    settings = get_settings_cached()

    if agent_prompt_path is None:
        agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

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

    return QueryProcessingTool(
        query_analyzer=get_query_analyzer_agent_tool(
            agent_prompt_path=agent_prompt_path
        ),
        eval_agent=get_evaluation_agent_tool(
            agent_prompt_path=agent_prompt_path
        ),
        memory_store=get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        ),
        settings=get_settings_cached(),
        llm_runner=google_llm.run,
        llm_arunner=google_llm.arun,
        prompt_path=agent_prompt_path,
        bot_name=bot_name
    )

def get_search_tool(
    bot_name: str,
):
    return SearchTool(
        openai_embedding=get_openai_embedding_cached(),
        qdrant_vector_store=get_qdrant_vector_store(
            collection_name=bot_name,
        ),
        mongodb_doc_store=get_mongodb_doc_store(
            database_name=bot_name,
            collection_name=bot_name,
        ),
    )
