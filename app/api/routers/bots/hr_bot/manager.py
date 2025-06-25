from fastapi import UploadFile, HTTPException, status

from services.agentic_workflow.bots.hr_bot import HrBotService
from api.routers.bots.base import BaseManager

from .handlers.files import (
    hr_get_files_metadata,
    hr_delete_file,
    hr_ocr_pdf_to_md
)


class HrBotManager(BaseManager):
    def __init__(
        self,
    ):
        self.hr_bot = HrBotService()

    # Chat
    async def chat(
        self,
    ):
        pass

    async def chat_stream(
        self,
    ):
        pass

    # File
    async def get_files_metadata(
        self,
    ):
        response = await hr_get_files_metadata(
            bot_service=self.hr_bot,
        )
        return response

    async def delete_file(
        self,
        file_name: str
    ):
        response = await hr_delete_file(
            bot_service=self.hr_bot,
            file_name=file_name
        )
        return response

    async def ocr_pdf_to_md(
        self,
        file: UploadFile
    ):
        response = await hr_ocr_pdf_to_md(
            bot_service=self.hr_bot,
            file=file
        )
        return response

    async def get_session(
        self,
    ):
        pass

    async def add_rating(
        self,

    ):
        pass

    async def get_logs(
        self,
        **kwargs,
    ):
        return [], 1
