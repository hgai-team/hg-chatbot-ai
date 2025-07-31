import logging
logger = logging.getLogger(__name__)

import io
import aiofiles
import asyncio
import mimetypes
import urllib.parse

from pathlib import Path
from typing import Callable, Union

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from openai.types.chat.chat_completion import ChatCompletion
from llama_index.core.llms import ChatResponse

from api.schema import DocumentType

from core.loaders import (
    ExcelReader,
    PandasExcelReader,
    PyMuPDFReader,
    DocxReader,
    MarkdownReader
)

from core.storages import (
    MongoDBDocumentStore,
    QdrantVectorStore
)

from core.embeddings import OpenAIEmbedding
from core.base import Document
from core.loaders.utils import get_visible_sheets
from core.parsers import parse_file, json_parser

from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool
from services import (
    get_settings_cached,
    get_google_genai_llm, GoogleGenAILLM,
    get_xai_llm, XAILLM
)

DEFAULT_SAVE_PATH = Path("./data")
CONCURRENT_LIMIT = 7

EXTRA_INFO_INCLUDE = [
    'tên network',
    'tên dự án',
    'quy_định_chung',
    'quy_định_chung_dự_án',
    'file_xlcv_chung_dự_án',
    'quy_định_riêng_dự_án_phòng_ban',
    'file_xlcv_riêng_dự_án_phòng_ban',
    'quy_định_riêng_dự_án_net',
    'file_xlcv_riêng_dự_án_net',
    'quy_định_network'
]

TEXT_EXCLUDE = [
    'quy_định_chung',
    'quy_định_chung_dự_án',
    'file_xlcv_chung_dự_án',
    'quy_định_riêng_dự_án_phòng_ban',
    'file_xlcv_riêng_dự_án_phòng_ban',
    'quy_định_riêng_dự_án_net',
    'file_xlcv_riêng_dự_án_net',
    'quy_định_network'
]

class FileProcessorTool:
    def __init__(
        self,
        bot_name: str
    ):
        self.bot_name = bot_name
        self._set_up()

    def _set_up(
        self
    ):
        from services import (
            get_excel_reader_cached,
            get_pandas_excel_reader_cached,
            get_pymupdf_reader_cached,
            get_docx_reader_cached,
            get_markdown_reader_cached,

            get_openai_embedding_cached,
            get_mongodb_doc_store,
            get_qdrant_vector_store
        )

        self.excel_reader: ExcelReader = get_excel_reader_cached()
        self.pandas_excel_reader: PandasExcelReader  = get_pandas_excel_reader_cached()
        self.pymupdf_reader: PyMuPDFReader = get_pymupdf_reader_cached()
        self.docx_reader: DocxReader = get_docx_reader_cached()
        self.md_reader: MarkdownReader = get_markdown_reader_cached()

        self.openai_embedding: OpenAIEmbedding = get_openai_embedding_cached()

        self.mongodb_doc_store: MongoDBDocumentStore = get_mongodb_doc_store(
            database_name=self.bot_name,
            collection_name=self.bot_name,
        )
        self.qdrant_vector_store: QdrantVectorStore = get_qdrant_vector_store(
            collection_name=self.bot_name,
        )

    async def chat(
        self,
        input_: str,
        model: Union[XAILLM, GoogleGenAILLM],
        agent_prompt_path: str,
        agent_name: str,
        func_name: str
    ):
        class_model_name = model.__class__.__name__

        async with asyncio.Semaphore(10):
            agent_config = PromptProcessorTool.load_prompt(agent_prompt_path)[agent_name]
            prompt_template = PromptProcessorTool.load_prompt(get_settings_cached().BASE_PROMPT_PATH)

            for cnt in range(1, 5):
                try:
                    if cnt > 1:
                        logger.info(f"Retry {func_name}: {cnt}")

                    prompt = PromptProcessorTool.apply_chat_template(
                        template=prompt_template,
                        **{**agent_config, **{"input": input_}}
                    )
                    messages = PromptProcessorTool.prepare_chat_messages(prompt=prompt)

                    if class_model_name == "XAILLM":
                        response: ChatCompletion = await model.arun(messages=messages)
                    elif class_model_name == "GoogleGenAILLM":
                        response: ChatResponse = await model.arun(messages=messages)

                    text_response = response.choices[0].message.content if class_model_name == "XAILLM" else response.message.content

                    json_response = json_parser(text_response)
                    if json_response.get("status", "") == "error":
                        json_response = text_response

                    return json_response
                except Exception as e:
                    logger.error(f"An unhandled error occurred in {func_name}: {e}", exc_info=True)
                    asyncio.sleep(cnt**2)

            return None

    async def ocr_to_md(
        self,
        file_path: str,
        agent_name: str
    ):
        from google import genai
        from google.genai import types


        client = genai.Client(api_key=get_settings_cached().GOOGLEAI_API_KEY)
        myfile = client.files.upload(file=file_path)

        prompts = PromptProcessorTool.load_prompt(get_settings_cached().BASE_PROMPT_PATH)
        agent = prompts[agent_name]
        system_prompt = (
            f"{agent['role']}"
            f"{agent['description']}"
            f"{agent['instructions']}"
        )

        for cnt in range(1, 5):
            try:
                if cnt > 1:
                    logger.info(f"Retry ocr_to_md: {cnt}")

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=get_settings_cached().GOOGLEAI_MODEL_THINKING,
                    contents=[myfile],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=65536,
                    )
                )

                return response.text
            except Exception as e:
                logger.error(f"An unhandled error occurred in ocr_to_md: {e}", exc_info=True)
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
            
    async def _save_file_streamed(
        self,
        file: UploadFile,
        save_directory: Path
    ) -> Path:
        save_directory.mkdir(parents=True, exist_ok=True)
        save_file_path = save_directory / file.filename

        async with aiofiles.open(save_file_path, mode='wb') as afp:
            while chunk := await file.read(1024 * 1024):  # 1MB chunk
                await afp.write(chunk)
        
        return save_file_path

    async def upload_excel_data(
        self,
        file: UploadFile,
        use_pandas=False,
        document_type: DocumentType = DocumentType.CHATBOT,
        extra_info_include=EXTRA_INFO_INCLUDE,
        text_exclude=TEXT_EXCLUDE
    ):
        file_name, file_stream = await parse_file(file)

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=BOT_SAVE_PATH
        )

        file_stream.seek(0)

        reader = self.pandas_excel_reader if use_pandas else self.excel_reader

        docs = reader.load_data(
            file=file_stream,
            sheet_name=get_visible_sheets(file_stream),
            extra_info={"file_name": file_name},
            extra_info_include=extra_info_include,
            text_exclude=text_exclude
        )

        tasks = [
            asyncio.create_task(self.store_docs(docs)),
            asyncio.create_task(self.embed_and_index_documents(docs)),
        ]

        _ = await asyncio.gather(*tasks)

        return {"status": 200}


    async def upload_pdf_data(
        self,
        file: UploadFile,
        document_type: DocumentType = DocumentType.CHATBOT,
    ):
        file_name, file_stream = await parse_file(file)

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=BOT_SAVE_PATH
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

    async def ocr_pdf_to_md(
        self,
        file: UploadFile,
        document_type: DocumentType = DocumentType.CHATBOT,
    ):
        # file_name, file_stream = await parse_file(file)
        file_name = file.filename

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)
        
        saved_file_path = await self._save_file_streamed(
            file=file,
            save_directory=BOT_SAVE_PATH
        )
        
        return saved_file_path

        # await self._save_file(
        #     file_stream=file_stream,
        #     file_name=file_name,
        #     save_directory=BOT_SAVE_PATH
        # )

        # content = await self.ocr_to_md(
        #     file_path=saved_file_path,#BOT_SAVE_PATH / file_name,
        #     agent_name='ocr_pdf_to_md_expert'
        # )

        # md_filename = Path(file_name).stem + ".md"
        # md_path = BOT_SAVE_PATH / md_filename

        # async with aiofiles.open(md_path, 'w', encoding='utf-8') as md_file:
        #     await md_file.write(content)

        # root_docs, leaf_docs = await asyncio.to_thread(
        #     self.md_reader.load_data,
        #     file=md_path,
        #     extra_info={"file_name": file_name}
        # )
        # all_docs = root_docs + leaf_docs

        # tasks = [
        #     self.chat(
        #         input_=f"""WHOLE_DOCUMENT:\n{content}\n\nCHUNK_CONTENT:\n{doc.get_content()}""",
        #         model=get_google_genai_llm(model_name=get_settings_cached().GOOGLEAI_MODEL),
        #         agent_prompt_path=get_settings_cached().BASE_PROMPT_PATH,
        #         agent_name='contextualizer',
        #         func_name='ocr_pdf_to_md'
        #     )
        #     for doc in all_docs
        # ]

        # ctxs = await asyncio.gather(*tasks, return_exceptions=True)

        # for idx, ctx in enumerate(ctxs):
        #     if not isinstance(ctx, Exception):
        #         doc: Document = all_docs[idx]
        #         doc.extra_info['contextualized_content'] = f"{ctx}\n\n{doc.get_content()}"
        #         doc.extra_info['original_content'] = doc.get_content()

        # leaf_docs = all_docs[len(root_docs):]

        # tasks = [
        #     asyncio.create_task(self.store_docs(all_docs)),
        #     asyncio.create_task(self.embed_and_index_documents(leaf_docs)),
        # ]

        # _ = await asyncio.gather(*tasks)

        # return {"status": 200}

    async def upload_docx_file(
        self,
        file: UploadFile,
        document_type: DocumentType = DocumentType.CHATBOT,
    ):
        file_name, file_stream = await parse_file(file)

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        await self._save_file(
            file_stream=file_stream,
            file_name=file_name,
            save_directory=BOT_SAVE_PATH
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
        document_type: DocumentType = DocumentType.CHATBOT,
    ):
        DEFAULT_SAVE_PATH = Path("./data")
        DEFAULT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        delete_file_path = BOT_SAVE_PATH / file_name

        md_filename = Path(file_name).stem + ".md"
        delete_md_path = BOT_SAVE_PATH / md_filename

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

            if delete_md_path.exists():
                delete_md_path.unlink()

            return {"status": 200}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting file data: {str(e)}"
            )

    async def get_file_data(
        self,
        file_name: str,
        document_type: DocumentType,
    ):
        DEFAULT_SAVE_PATH = Path("./data")
        DEFAULT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        BOT_SAVE_PATH = DEFAULT_SAVE_PATH / self.bot_name / document_type.name
        BOT_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        file_path = BOT_SAVE_PATH / file_name

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File doesn't exists"
            )

        media_type, _ = mimetypes.guess_type(str(file_path))
        media_type = media_type or "application/octet-stream"

        filename_quoted = urllib.parse.quote(file_name)

        content_disposition = (
            f"inline; filename*=UTF-8''{filename_quoted}"
        )

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            headers={"Content-Disposition": content_disposition}
        )

    async def store_docs(
        self,
        docs
    ):
        try:
            for idx in range(len(docs)):
                doc: Document = docs[idx]
                if 'contextualized_content' in doc.extra_info:
                    doc.set_content(doc.extra_info['contextualized_content'])

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
            for idx in range(len(docs)):
                doc: Document = docs[idx]
                if 'contextualized_content' in doc.extra_info:
                    doc.set_content(doc.extra_info['contextualized_content'])

            docs_with_embedding = await asyncio.to_thread(self.openai_embedding.get_embeddings, docs)
            _ = await self.qdrant_vector_store.add(docs_with_embedding)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error embedding and indexing: {str(e)}"
            )
