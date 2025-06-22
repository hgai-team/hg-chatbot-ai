import io
import aiofiles
import asyncio
import logging
logger = logging.getLogger(__name__)

from pathlib import Path

from fastapi import HTTPException, UploadFile

from core.loaders import (
    ExcelReader,
    PandasExcelReader,
    PyMuPDFReader,
    DocxReader
)

from core.storages import (
    MongoDBDocumentStore,
    QdrantVectorStore
)

from core.embeddings import OpenAIEmbedding

from core.loaders.utils import get_visible_sheets
from core.parsers import parse_file

DEFAULT_SAVE_PATH = Path("./data")
CONCURRENT_LIMIT = 7

class FileProcessorTool:
    def __init__(
        self,
        excel_reader = ExcelReader,
        pandas_excel_reader = PandasExcelReader,
        pymupdf_reader = PyMuPDFReader,
        docx_reader = DocxReader,

        openai_embedding = OpenAIEmbedding,

        mongodb_doc_store = MongoDBDocumentStore,
        qdrant_vector_store = QdrantVectorStore,
    ):
        self.excel_reader = excel_reader
        self.pandas_excel_reader = pandas_excel_reader
        self.pymupdf_reader = pymupdf_reader
        self.docx_reader = docx_reader

        self.openai_embedding = openai_embedding

        self.mongodb_doc_store: MongoDBDocumentStore = mongodb_doc_store
        self.qdrant_vector_store = qdrant_vector_store

    async def ops_bot_get_context_data(
        self
    ):
        from api.routers.bots.ops_bot.handlers.master_data import get_all_master_data

        context_data = {}
        response = await get_all_master_data()
        
        for result in response:
            if result.type not in context_data:
                context_data[result.type] = [result.name]
            else:
                context_data[result.type].append(result.name)

        return context_data

    async def ops_bot_find_type(
        self,
        input_text,
        context_data
    ):
        from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool

        from services import get_openai_llm, get_settings_cached
        from core.parsers import json_parser
        
        openai_llm = get_openai_llm(
            model_name=get_settings_cached().OPENAI_CHAT_MODEL
        )
        
        cnt = 0
        while cnt < 5:
            try:
                if cnt > 0:
                    logger.info(f"Retry ops_bot_find_type: {cnt}")
                agent_config = PromptProcessorTool.load_prompt(get_settings_cached().OPS_AGENT_PROMPT_PATH)['information_classifier']
                prompt_template = PromptProcessorTool.load_prompt(get_settings_cached().BASE_PROMPT_PATH)

                input_ = f"context_data:\n{context_data}\n\ninput_text:\n{input_text}\n"
                prompt = PromptProcessorTool.apply_chat_template(
                    template=prompt_template,
                    **{**agent_config, **{"input": input_}}
                )
                messages = PromptProcessorTool.prepare_chat_messages(prompt=prompt)
                response = await openai_llm.arun(messages)
                json_response = json_parser(response)
                
                return json_response
            except Exception as e:
                cnt += 1
                logger.error(f"An unhandled error occurred in ops_bot_find_type: {e}", exc_info=True)
                continue
        
        return None
        
    async def _save_file(
        self,
        file_stream: io.BytesIO,
        file_name: str,
        save_directory: Path
    ) -> Path:
        save_directory.mkdir(parents=True, exist_ok=True)

        save_file_path = save_directory / file_name

        async with aiofiles.open(save_file_path, mode='wb') as afp:
            await afp.write(file_stream.getvalue())


    async def upload_excel_data(
        self,
        file: UploadFile,
        use_pandas=False,
        use_type=True,
    ):
        file_name, file_stream = await parse_file(file)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=DEFAULT_SAVE_PATH
        )

        file_stream.seek(0)

        reader = self.pandas_excel_reader if use_pandas else self.excel_reader

        docs = reader.load_data(
            file=file_stream,
            sheet_name=get_visible_sheets(file_stream),
            extra_info={"file_name": file_name}
        )

        if use_type and docs:
            context_data = await self.ops_bot_get_context_data()
            
            semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
            
            async def process_and_update_doc(doc):
                async with semaphore:
                    try:
                        extra_info = await self.ops_bot_find_type(doc.text, context_data)
                        if extra_info:
                            doc.extra_info = {**doc.extra_info, **extra_info}
                    except Exception as e:
                        logger.error(f"Failed to process doc text: '{doc.text[:50]}...' due to {e}")
                    return doc
                
            tasks = [process_and_update_doc(doc) for doc in docs]
            updated_docs = await asyncio.gather(*tasks)
            docs = updated_docs

        tasks = [
            asyncio.create_task(self.store_docs(docs)),
            asyncio.create_task(self.embed_and_index_documents(docs)),
        ]

        _ = await asyncio.gather(*tasks)

        return {"status": 200}


    async def upload_pdf_data(
        self,
        file: UploadFile,
    ):
        file_name, file_stream = await parse_file(file)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=DEFAULT_SAVE_PATH
        )

        file_stream.seek(0)

        docs = self.pymupdf_reader.load_data(
            file=file_stream,
            extra_info={"file_name": file_name}
        )

        tasks = [
            asyncio.create_task(self.store_docs(docs)),
            asyncio.create_task(self.embed_and_index_documents(docs)),
        ]

        _ = await asyncio.gather(*tasks)

        return {"status": 200}

    async def upload_and_convert_pdf_to_md(
        self,
        file: UploadFile,
    ):
        # from services import (
        #     get_google_genai_llm,
        #     get_settings_cached
        # )
        # google_llm = get_google_genai_llm(
        #     model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING
        # )
        file_name, file_stream = await parse_file(file)

        # await self._save_file(
        #     file_stream=file_stream,
        #     file_name=file_name,
        #     save_directory=DEFAULT_SAVE_PATH
        # )

        save_file_path = DEFAULT_SAVE_PATH / file_name

        return save_file_path

        # file_stream.seek(0)

        # docs = self.pymupdf_reader.load_data(
        #     file=file_stream,
        #     extra_info={"file_name": file_name}
        # )

        # tasks = [
        #     asyncio.create_task(self.store_docs(docs)),
        #     asyncio.create_task(self.embed_and_index_documents(docs)),
        # ]

        # _ = await asyncio.gather(*tasks)

        # return {"status": 200}

    async def upload_docx_file(
        self,
        file: UploadFile,
    ):
        file_name, file_stream = await parse_file(file)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=DEFAULT_SAVE_PATH
        )

        file_stream.seek(0)

        docs = self.docx_reader.load_data(
            file=file_stream,
            extra_info={"file_name": file_name}
        )

        tasks = [
            asyncio.create_task(self.store_docs(docs)),
            asyncio.create_task(self.embed_and_index_documents(docs)),
        ]

        _ = await asyncio.gather(*tasks)

        return {"status": 200}

    async def delete_file_data(
        self,
        file_name: str,
    ):
        DEFAULT_SAVE_PATH = Path("./data")
        DEFAULT_SAVE_PATH.mkdir(parents=True, exist_ok=True)
        delete_file_path = DEFAULT_SAVE_PATH / file_name

        try:
            cursor = self.mongodb_doc_store.collection.find({"attributes.file_name": file_name}, {"id": 1, "_id": 0})
            docs_to_delete = await cursor.to_list(length=None)

            deleted_ids = []
            for doc in docs_to_delete:
                deleted_ids.append(doc.get("id"))

            if deleted_ids:
                tasks = [
                    asyncio.create_task(self.mongodb_doc_store.delete(deleted_ids)),
                    asyncio.create_task(self.qdrant_vector_store.delete(deleted_ids)),
                ]

                _ = await asyncio.gather(*tasks)

            if delete_file_path.exists():
                delete_file_path.unlink()

            return {"status": 200}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting file data: {str(e)}"
            )

    async def store_docs(
        self,
        docs
    ):
        try:
            _ = await self.mongodb_doc_store.add(docs)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error storing documents: {str(e)}"
            )

    async def embed_and_index_documents(
        self,
        docs
    ):
        try:
            docs_with_embedding = await asyncio.to_thread(self.openai_embedding.get_embeddings, docs)
            _ = await self.qdrant_vector_store.add(docs_with_embedding)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error embedding and indexing: {str(e)}"
            )
