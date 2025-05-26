from functools import lru_cache

from core.config import get_core_settings
from core.embeddings import OpenAIEmbedding
from core.llms import OpenAILLM, GoogleGenAILLM
from core.storages import (
    QdrantVectorStore,
    MongoDBMemoryStore,
    MongoDBDocumentStore
)
from core.loaders import (
    ExcelReader,
    PandasExcelReader,
    PyMuPDFReader,
    DocxReader
)
from langfuse.llama_index import LlamaIndexInstrumentor
from qdrant_client import QdrantClient



@lru_cache
def get_settings_cached():
    return get_core_settings()

@lru_cache
def get_openai_embedding_cached(
    api_key: str = None,
    model_name: str = None,
):
    settings = get_settings_cached()

    if api_key is None:
        api_key = settings.OPENAI_API_KEY
    if model_name is None:
        model_name = settings.OPENAI_TEXT_EMBEDDING_MODEL

    return OpenAIEmbedding(api_key=api_key, model_name=model_name)

def get_qdrant_vector_store(
    host: str = None,
    port: int = None,
    collection_name: str = None,
):
    settings = get_settings_cached()

    if host is None:
        host = settings.QDRANT_HOST
    if port is None:
        port = settings.QDRANT_PORT

    if collection_name is None:
        collection_name = settings.QDRANT_BASE_COLLECTION_NAME
    elif not collection_name.endswith(settings.QDRANT_BASE_COLLECTION_NAME):
        collection_name = f"{collection_name}{settings.QDRANT_BASE_COLLECTION_NAME}"

    qdrant_client = QdrantClient(host=host, port=port)

    return QdrantVectorStore(collection_name=collection_name, client=qdrant_client)

def get_mongodb_memory_store(
    connection_string: str = None,
    database_name: str = None,
    collection_name: str = None,
):
    settings = get_settings_cached()

    if connection_string is None:
        connection_string = settings.MONGODB_CONNECTION_STRING

    if database_name is None:
        database_name = settings.MONGODB_BASE_DATABASE_NAME
    elif not database_name.endswith(settings.MONGODB_BASE_DATABASE_NAME):
        database_name = f"{database_name}{settings.MONGODB_BASE_DATABASE_NAME}"

    if collection_name is None:
        collection_name = settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME
    elif not collection_name.endswith(settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME):
        collection_name = f"{collection_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"

    return MongoDBMemoryStore(
        connection_string=connection_string,
        database_name=database_name,
        collection_name=collection_name,
    )

def get_mongodb_doc_store(
    connection_string: str = None,
    database_name: str = None,
    collection_name: str = None,
):
    settings = get_settings_cached()

    if connection_string is None:
        connection_string = settings.MONGODB_CONNECTION_STRING

    if database_name is None:
        database_name = settings.MONGODB_BASE_DATABASE_NAME
    elif not database_name.endswith(settings.MONGODB_BASE_DATABASE_NAME):
        database_name = f"{database_name}{settings.MONGODB_BASE_DATABASE_NAME}"

    if collection_name is None:
        collection_name = settings.MONGODB_BASE_DOC_COLLECTION_NAME
    elif not collection_name.endswith(settings.MONGODB_BASE_DOC_COLLECTION_NAME):
        collection_name = f"{collection_name}{settings.MONGODB_BASE_DOC_COLLECTION_NAME}"

    return MongoDBDocumentStore(
        connection_string=connection_string,
        database_name=database_name,
        collection_name=collection_name,
    )

def get_openai_llm(
    api_key: str = None,
    model_name: str = None,
):
    settings = get_settings_cached()

    if api_key is None:
        api_key = settings.OPENAI_API_KEY
    if model_name is None:
        model_name = settings.OPENAI_CHAT_MODEL

    return OpenAILLM(api_key=api_key, model_name=model_name)


def get_google_genai_llm(
    api_key: str = None,
    model_name: str = None,
):
    settings = get_settings_cached()

    if api_key is None:
        api_key = settings.GOOGLEAI_API_KEY
    if model_name is None:
        model_name = settings.GOOGLEAI_MODEL

    return GoogleGenAILLM(api_key=api_key, model_name=model_name)

@lru_cache
def get_langfuse_instrumentor_cached():
    settings = get_settings_cached()

    return LlamaIndexInstrumentor(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        environment=settings.LANGFUSE_TRACING_ENVIRONMENT,
    )

@lru_cache
def get_excel_reader_cached():
    return ExcelReader()

@lru_cache
def get_pandas_excel_reader_cached():
    return PandasExcelReader()

@lru_cache
def get_pymupdf_reader_cached():
    return PyMuPDFReader()

@lru_cache
def get_docx_reader_cached():
    return DocxReader()
