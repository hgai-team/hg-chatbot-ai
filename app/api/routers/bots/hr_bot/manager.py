from services.agentic_workflow.bots.hr_bot import HrBotService
from api.routers.bots.base import BaseManager

class HrBotManager(BaseManager):
    def __init__(
        self,
    ):
        self.hr_bot = HrBotService()

    async def chat(
        self,
    ):
        pass

    async def chat_stream(
        self,
    ):
        pass

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
