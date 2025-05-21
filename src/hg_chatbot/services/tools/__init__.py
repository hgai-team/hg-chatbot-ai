from services import (
    get_excel_reader_cached,
    get_pandas_excel_reader_cached,
    get_pymupdf_reader_cached,
    get_docx_reader_cached,

    get_openai_embedding_cached,

    get_qdrant_vector_store,
    get_mongodb_doc_store,
)


from .bm25 import BM25Retriever

from .files import (
    FileProcessorTool
)

from .prompt import (
    apply_chat_template,
    load_prompt,
    prepare_chat_messages
)

from .search import (
    SearchTool
)


def get_file_processor_tool(
    bot_name: str,
):
    return FileProcessorTool(
        excel_reader=get_excel_reader_cached(),
        pandas_excel_reader=get_pandas_excel_reader_cached(),
        pymupdf_reader=get_pymupdf_reader_cached(),
        docx_reader=get_docx_reader_cached(),

        openai_embedding=get_openai_embedding_cached(),

        mongodb_doc_store=get_mongodb_doc_store(
            database_name=bot_name,
            collection_name=bot_name,
        ),
        qdrant_vector_store=get_qdrant_vector_store(
            collection_name=bot_name,
        ),
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

