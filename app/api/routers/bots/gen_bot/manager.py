import io
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import UploadFile, HTTPException, status

from google import genai
from google.genai import types

from services.agentic_workflow.bots.gen_bot import GenBotService
from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services import get_settings_cached

from api.routers.bots.base import BaseManager
from api.schema import (
    ChatRequest
)

from .handlers.chat import (
    gen_chat_stop,
    gen_chat,
    gen_chat_stream
)


class GenBotManager(BaseManager):
    def __init__(
        self,
    ):
        self.gen_bot = GenBotService()
        self.client = genai.Client(
            api_key=get_settings_cached().GOOGLEAI_API_KEY
        )

    # Chat
    async def chat_stop(
        self,
        chat_id: str,
    ):
        await gen_chat_stop(
            bot_service=self.gen_bot,
            chat_id=chat_id,
        )

    async def chat(
        self,
        chat_request: ChatRequest,
    ):
        pass

    async def chat_stream(
        self,
        chat_request: ChatRequest,
    ):
        async for chunk in gen_chat_stream(
            bot_service=self.gen_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id,
            selected_tool=chat_request.selected_tool
        ):
            yield chunk

    # Session
    async def get_session(
        self,
        session_id: str
    ):
        response = await self.gen_bot.memory_store.get_session_history(
            session_id=session_id
        )
        return response

    async def add_rating(
        self,
        chat_id: str,
        rating_type: str = None,
        rating_text: str = None,
    ):
        await self.gen_bot.memory_store.add_rating(
            chat_id=chat_id,
            rating_type=rating_type,
            rating_text=rating_text
        )

    async def count_tokens(
        self,
        session_id: str,
        message: str
    ):
        session_his = await self.gen_bot.memory_store.get_session_history(
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
                "totalTokens": 0,
                "cachedContentTokenCount": None
            }

        return self.client.models.count_tokens(
            model=get_settings_cached().GOOGLEAI_MODEL_THINKING,
            contents=contents
        )

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
        logs = await self.gen_bot.memory_store.get_logs(
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
        logs = await self.gen_bot.memory_store.get_logs()
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
        his_sessions = await self.gen_bot.memory_store.get_user_sessions(
            user_id=user_id,
        )
        return sum([len(chat) for chat in his_sessions])
