import io
import asyncio
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import UploadFile, HTTPException, status
from google import genai
from google.genai import types

from services import get_settings_cached
from services.agentic_workflow.bots.hr_bot import HrBotService
from api.routers.bots.base import BaseManager
from api.schema import (
    ChatRequest,
    DocumentType
)

from .handlers.chat import (
    hr_chat_stop,
    hr_chat,
    hr_chat_stream
)

from .handlers.files import (
    hr_ocr_pdf_to_md,

    get_files_metadata,
    get_file,
    delete_file,
)


class HrBotManager(BaseManager):
    def __init__(
        self,
    ):
        self.hr_bot = HrBotService()
        self.client = genai.Client(
            api_key=get_settings_cached().GOOGLEAI_API_KEY
        )

    # Chat
    async def chat_stop(
        self,
        chat_id: str,
    ):
        await hr_chat_stop(
            bot_service=self.hr_bot,
            chat_id=chat_id,
        )

    async def chat(
        self,
        chat_request: ChatRequest,
    ):
        return await hr_chat(
            bot_service=self.hr_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id
        )

    async def chat_stream(
        self,
        chat_request: ChatRequest,
    ):
        async for chunk in hr_chat_stream(
            bot_service=self.hr_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id
        ):
            yield chunk

    # File
    async def get_files_metadata(
        self,
        document_type: DocumentType,
        q: str,
        limit: int,
        page_index: int,
        file_ext: list[str],
        sort_field: str,
        sort_order: int
    ):
        response = await get_files_metadata(
            bot_name=self.hr_bot.bot_name,
            document_type=document_type,
            q=q,
            limit=limit,
            page_index=page_index,
            file_ext=file_ext,
            sort_field=sort_field,
            sort_order=sort_order
        )
        return response

    async def delete_file(
        self,
        file_ids: list[UUID]
    ):
        response = await delete_file(
            file_processor=self.hr_bot.file_processor,
            file_ids=file_ids
        )
        return response

    async def get_file(
        self,
        file_id: UUID
    ):
        response = await get_file(
            file_processor=self.hr_bot.file_processor,
            file_id=file_id
        )
        return response

    async def ocr_pdf_to_md(
        self,
        email: str,
        file: UploadFile,
        document_type: DocumentType = DocumentType.CHATBOT
    ):
        response = await hr_ocr_pdf_to_md(
            bot_service=self.hr_bot,
            email=email,
            file=file,
            document_type=document_type
        )
        return response

    # Session
    async def get_session(
        self,
        session_id: str
    ):
        response = await self.hr_bot.memory_store.get_session_history(
            session_id=session_id
        )
        return response

    async def add_rating(
        self,
        chat_id: str,
        rating_type: str = None,
        rating_text: str = None,
    ):
        await self.hr_bot.memory_store.add_rating(
            chat_id=chat_id,
            rating_type=rating_type,
            rating_text=rating_text
        )

    async def count_tokens(
        self,
        session_id: str,
        message: str,
        video_url: str = None,
        start_offset: str = None,
        end_offset: str = None,
        fps: int = 1,
    ):
        from core.mcp.vid_ytb import count_video_tokens
        
        total_video_tokens = 0
        if video_url:
            total_video_tokens = await count_video_tokens(
                video_url,
                start_offset,
                end_offset,
                fps,
            ) 
        
        session_his = await self.hr_bot.memory_store.get_session_history(
            session_id=session_id
        )

        extra_content = []
        if message:
            extra_content = [types.Content(role="user", parts=[types.Part(text=message)])]

        contents = [
            types.Content(role=role, parts=[types.Part(text=text if text else "")])
            for record in session_his.history
            for role, text in (("user", record["message"]), ("model", record["response"]))
        ]

        if extra_content:
            contents = contents + extra_content

        if not contents:
            return {
                "total_tokens": total_video_tokens,
                "cached_content_token_count": None,
                "max_tokens": 512000
            }
            
        try:
            resp = await asyncio.to_thread(
                self.client.models.count_tokens,
                model=get_settings_cached().GOOGLEAI_MODEL_THINKING,
                contents=contents
            )
        except Exception as e:
            raise
        
        resp_dict = resp.model_dump()
        resp_dict["total_tokens"] = resp_dict.get("total_tokens", 0) + total_video_tokens
        resp_dict["max_tokens"] = 512000
        return resp_dict

    # Logs
    async def get_logs(
        self,
        page_index: int,
        limit: int,
        rating_type: list[str],
        st: str,
        et: str,
        so: int
    ):
        results = []
        logs = await self.hr_bot.memory_store.get_logs(
            rating_type=rating_type,
            st=st,
            et=et,
        )
        try:
            if len(logs) == 0:
                return [], {'page_number': 0, 'total_items': 0}


            for log in logs:
                for history in log.history:
                    results.append({
                        "user_id": log.user_id,
                        "session_id": log.session_id,
                        "message": history["message"],
                        "response": history["response"],
                        "status": history.get("status", None),
                        "timestamp": history["timestamp"].replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Bangkok")),
                        "chat_id": history["chat_id"],
                        "rating_type": history["rating_type"],
                        "rating_text": history["rating_text"],
                        "metadata": history.get("metadata", {})
                    })

            if so:
                reverse = so == -1
                results.sort(key=lambda x: x.get("timestamp"), reverse=reverse)

            page_number = len(results) / limit
            if not float(page_number) == int(page_number):
                page_number = int(page_number) + 1

            if page_index > page_number:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"page_index must be less than page_number"
                )

            return results[(page_index - 1) * limit: page_index * limit], {'page_number': page_number, 'total_items': len(results)}

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing logs: {str(e)}"
            )

    async def get_logs_file(
        self,
    ):
        results = []
        logs = await self.hr_bot.memory_store.get_logs()
        try:
            if len(logs) == 0:
                return [], {'page_number': 0, 'total_items': 0}


            for log in logs:
                for history in log.history:
                    ts_bkk_naive = (
                        history["timestamp"]
                        .replace(tzinfo=timezone.utc)
                        .astimezone(ZoneInfo("Asia/Bangkok"))
                        .replace(tzinfo=None)
                    )

                    results.append({
                        "user_id": log.user_id,
                        "session_id": log.session_id,
                        "message": history["message"],
                        "response": history["response"],
                        "timestamp": ts_bkk_naive,
                        "chat_id": history["chat_id"],
                        "rating_type": history["rating_type"],
                        "rating_text": history["rating_text"]
                    })

            df = pd.DataFrame(results)

            file = io.BytesIO()
            with pd.ExcelWriter(file, engine='openpyxl') as writer:
                ts = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y%m%d_%H%M")
                sheet_name = f"history_{ts}"[:31]
                df.to_excel(writer, index=False, sheet_name=sheet_name)
            file.seek(0)

            return file, ts

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing logs: {str(e)}"
            )

    async def get_user_sys_resp_cnt(
        self,
        user_id: str
    ):
        his_sessions = await self.hr_bot.memory_store.get_user_sessions(
            user_id=user_id,
        )
        return sum([len(chat) for chat in his_sessions])
