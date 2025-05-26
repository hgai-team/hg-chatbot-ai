import io
import aiofiles
import asyncio

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

        self.mongodb_doc_store = mongodb_doc_store
        self.qdrant_vector_store = qdrant_vector_store

    async def _get_context_data(
        self
    ):
        from api.routers.vahacha.info_permission import get_all_data

        context_data = {}
        response = await get_all_data()
        for result in response['results']:
            if result.type not in context_data:
                context_data[result.type] = [result.name]
            else:
                context_data[result.type].append(result.name)

        return context_data

    async def _find_type(
        self,
        input_text,
        context_data
    ):
        from services.tools.prompt import (
            load_prompt,
            apply_chat_template,
            prepare_chat_messages
        )

        from services import get_openai_llm, get_settings_cached
        from core.parsers import json_parser

        openai_llm = get_openai_llm(
            model_name=get_settings_cached().OPENAI_CHAT_MODEL
        )

        agent_config = load_prompt(get_settings_cached().VAHACHA_AGENT_PROMPT_PATH)['information_classifier']
        prompt_template = load_prompt(get_settings_cached().BASE_PROMPT_PATH)

        input_ = f"context_data:\n{context_data}\n\ninput_text:\n{input_text}\n"
        prompt = apply_chat_template(
            template=prompt_template,
            **{**agent_config, **{"input": input_}}
        )
        messages = prepare_chat_messages(prompt=prompt)
        response = await openai_llm.arun(messages)

        return json_parser(response)

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

        if use_type:
            context_data = await self._get_context_data()
            for i, doc in enumerate(docs):
                extra_info = await self._find_type(doc.text, context_data)
                docs[i].extra_info = {**doc.extra_info, **extra_info}

        tasks = [
            asyncio.create_task(self.store_docs(docs)),
            asyncio.create_task(self.embed_and_index_documents(docs)),
            # asyncio.create_task(self.bm25_retriever.add_document(docs))
        ]

        _ = await asyncio.gather(*tasks)

        # self.bm25_retriever.save_index()

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

            docs_to_delete = list(self.mongodb_doc_store.collection.find({"attributes.file_name": file_name}, {"id": 1, "_id": 0}))

            deleted_ids = []
            for doc in docs_to_delete:
                deleted_ids.append(doc.get("id"))


            if deleted_ids:
                tasks = [
                    asyncio.create_task(self.mongodb_doc_store.delete(deleted_ids)),
                    asyncio.create_task(self.qdrant_vector_store.delete(deleted_ids)),
                    # asyncio.create_task(self.bm25_retriever.delete_by_file_name(file_name))
                ]

                _ = await asyncio.gather(*tasks)

                # self.bm25_retriever.save_index()

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
            docs_with_embedding = self.openai_embedding.get_embeddings(docs)
            _ = await self.qdrant_vector_store.add(docs_with_embedding)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error embedding and indexing: {str(e)}"
            )
