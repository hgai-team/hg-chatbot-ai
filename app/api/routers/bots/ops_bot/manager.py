import io
import pandas as pd

from fastapi import UploadFile, HTTPException, status
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .handlers.chat import (
    ops_chat,
    ops_chat_stream,
    ops_chat_user_stream,
)

from .handlers.files import (
    ops_get_files_metadata,
    ops_delete_file,
    ops_upload_excel
)


from services.agentic_workflow.bots.ops_bot import OpsBotService
from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool as PPT
from api.routers.bots.base import BaseManager
from api.schema import (
    ChatRequest, UserContext,
    AgentRequest
)

class OpsBotManager(BaseManager):
    def __init__(
        self,
    ):
        self.ops_bot = OpsBotService()

    async def chat(
        self,
        chat_request: ChatRequest,
    ):
        return await ops_chat(
            chat_service=self.ops_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id
        )

    async def chat_stream(
        self,
        chat_request: ChatRequest,
    ):
        async for chunk in ops_chat_stream(
            chat_service=self.ops_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id
        ):
            yield chunk

    async def chat_user_stream(
        self,
        chat_request: ChatRequest,
        email: str,
    ):
        async for chunk in ops_chat_user_stream(
            chat_service=self.ops_bot,
            query_text=chat_request.query_text,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id,
            email=email
        ):
            yield chunk

    async def get_files_metadata(
        self,
    ):
        response = await ops_get_files_metadata(
            ops_bot_service=self.ops_bot,
        )
        return response

    async def delete_file(
        self,
        file_name: str
    ):
        response = await ops_delete_file(
            file_service=self.ops_bot,
            file_name=file_name
        )
        return response

    async def upload_excel(
        self,
        file: UploadFile,
        use_type: bool = False,
        use_pandas: bool = False
    ):
        response = await ops_upload_excel(
            file_service=self.ops_bot,
            file=file,
            use_type=use_type,
            use_pandas=use_pandas
        )
        return response

    async def get_session(
        self,
        session_id: str
    ):
        response = await self.ops_bot.memory_store.get_session_history(
            session_id=session_id
        )
        return response

    async def add_rating(
        self,
        chat_id: str,
        rating_type: str = None,
        rating_text: str = None,
    ):
        await self.ops_bot.memory_store.add_rating(
            chat_id=chat_id,
            rating_type=rating_type,
            rating_text=rating_text
        )

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
        logs = await self.ops_bot.memory_store.get_logs(
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
        logs = await self.ops_bot.memory_store.get_logs()
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

    async def agent_evaluation(
        self,
        agent_request: AgentRequest,
        user_context: UserContext = None
    ):
        if not agent_request.agent_name in list(PPT.load_prompt(self.ops_bot.agent_prompt_path).keys()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Not found agent: {agent_request.agent_name}"
            )

        if agent_request.agent_name in ["safety_guard", "query_preprocessor", "keyword_extractor"]:
            query = agent_request.query_text.lower()
        elif agent_request.agent_name == "query_classifier":
            query = f"""user_query:\n{agent_request.query_text.lower()}\n\nuser_context:\n{user_context.model_dump_json().lower()}"""
        else:
            query = f"""question:\n{agent_request.query_text.lower()}\nquestion_context:\n{agent_request.response_text}\n\nuser_context:\n{user_context.model_dump_json(exclude='role').lower()}""",

        response = await self.ops_bot.eval_agent.validate(
            query=query,
            user_id=agent_request.agent_name,
            session_id=agent_request.agent_name,
            func=self.ops_bot.google_llm.arun,
            agent_name=agent_request.agent_name
        )

        return response
