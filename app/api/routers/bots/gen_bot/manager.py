import io
import asyncio
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
        message: str,
        video_url: str = None,
        start_offset: str = None,
        end_offset: str = None,
        fps: int = 1,
    ):
        from api.routers.bots.tools.tokens import count_text_tokens
        from core.mcp.vid_ytb import count_video_tokens

        total_video_tokens = 0
        if video_url:
            total_video_tokens = await count_video_tokens(
                video_url,
                start_offset,
                end_offset,
                fps,
            )

        session_his = await self.gen_bot.memory_store.get_session_history(
            session_id=session_id
        )

        messages = ""
        if message:
            messages += f"{message}\n\n"

        for record in session_his.history:
            for text in [record["message"], record["response"]]:
                messages += f"{text}\n\n"

        if not messages:
            return {
                "total_tokens": total_video_tokens,
                "total_video_tokens": total_video_tokens,
                "cached_content_token_count": None,
                "max_tokens": 512000
            }

        try:
            resp = await count_text_tokens(text=messages)
        except Exception as e:
            raise e

        resp_dict = {}
        resp_dict["total_tokens"] = resp.get("token_count", 0) + total_video_tokens
        resp_dict["total_video_tokens"] = total_video_tokens
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
