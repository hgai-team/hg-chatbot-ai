import asyncio
from api.endpoints import app as api_app

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import create_db_and_tables
from core.discord import client
from core.config import get_core_settings
import logging

from contextlib import asynccontextmanager

logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    from core.discord.bot import message_queue, workers, thread_pool

    bot_task = asyncio.create_task(client.start(get_core_settings().DISCORD_BOT_TOKEN))
    logger.info("Discord bot started")

    yield

    logger.info("Shutting down Discord bot...")
    if client.is_ready():
        await client.close()

    logger.info("Waiting for message queue to finish processing...")
    try:
        await asyncio.wait_for(message_queue.join(), timeout=30)
    except asyncio.TimeoutError:
        logger.warning("Timed out waiting for message queue to finish")

    logger.info("Cancelling message queue workers...")
    for worker in workers:
        worker.cancel()

    await asyncio.gather(*workers, return_exceptions=True)

    logger.info("Shutting down thread pool...")
    thread_pool.shutdown(wait=False)

    if not bot_task.done():
        logger.info("Cancelling Discord bot task...")
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            logger.info("Discord bot task cancelled")

app = FastAPI(lifespan=lifespan)
app.include_router(api_app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def main():
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting HG Chatbot...")

    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000
    )

if __name__ == "__main__":
    main()



