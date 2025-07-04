from typing import Dict
from functools import lru_cache
from fastapi import HTTPException, status

from api.routers.bots.hr_bot import HrBotManager
from api.routers.bots.ops_bot import OpsBotManager
from api.routers.bots.gen_bot import GenBotManager
from api.routers.bots.base import BaseManager

BOT_MANAGER_CLASSES: Dict[str, type] = {
    "VaHaCha": OpsBotManager,
    "ChaChaCha": HrBotManager,
    "HGGPT": GenBotManager
}

@lru_cache(maxsize=None)
def get_bot_manager(bot_name: str) -> BaseManager:
    cls = BOT_MANAGER_CLASSES.get(bot_name)
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
    return cls()
