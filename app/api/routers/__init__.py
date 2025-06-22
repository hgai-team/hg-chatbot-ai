from .bots.bots import app as bots_router
from .bots.ops import app as ops_router

from .auth import app as auth_router

__all__ = [
    "bots_router",
    'ops_router',

    "auth_router",
]
