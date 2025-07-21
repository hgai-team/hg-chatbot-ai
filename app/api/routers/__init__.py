from .bots.bots import app as bots_router

from .auth import app as auth_router

__all__ = [
    "bots_router",

    "auth_router",
]
