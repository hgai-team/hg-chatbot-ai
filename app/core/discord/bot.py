import os
import json
import discord
import asyncio
import time
import logging
import concurrent.futures

from collections import defaultdict
from fastapi import Depends
from starlette.responses import StreamingResponse

# import endpoint và schema từ FastAPI
from api.routers.bots.ops_bot.handlers.chat import ops_chat_user_stream, ops_chat_stream
from api.routers.bots.bots import chat_user_stream, chat_stream
from api.schema import ChatRequest, UserContext



from api.config import get_api_settings
from core.config import get_core_settings
from core.base import Document

from llama_index.core.node_parser import SentenceSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# hàng đợi và rate limit
message_queue = asyncio.Queue()
user_last_message = defaultdict(float)
user_message_count = defaultdict(int)

workers = []
# pool thread để xử lý chặn
thread_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=get_core_settings().DISCORD_BOT_NUM_WORKERS * 2,
    thread_name_prefix="discord_bot_worker"
)

sentence_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=0)


async def run_in_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, func, *args, **kwargs)


async def process_message_queue():
    while True:
        message, prompt = await message_queue.get()
        asyncio.create_task(process_single_message(message, prompt))
        message_queue.task_done()

def split_chunks(text: str, size: int = 1999):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        newline = text.rfind("\n", start, end)
        if newline > start:
            end = newline + 1
        chunks.append(text[start:end])
        start = end
    return chunks

async def process_single_message(message: discord.Message, prompt: str):
    """
    Với mỗi message trigger, chúng ta sẽ gọi stream_generator từ FastAPI
    và đọc dần các SSE chunks, rồi đẩy về Discord.
    """
    try:
        # Gửi trước một DM reply để edit dần
        logger.info(f"Getting response for user {message.author.id}")
        bot_message = await message.author.send("⏳ Đang khởi tạo phiên chat...")
        thinking_content = ""
        response_content = ""
        in_response = False

        user_context = await fetch_user_context_obj(message.author.id)

        # Chuẩn bị ChatRequest
        chat_request = ChatRequest(
            user_id=str(message.author.id),
            session_id=f"discord-{message.author.id}",
            query_text=prompt,
        )

        # Gọi FastAPI endpoint
        if user_context.role != 'admin':
            streaming_resp: StreamingResponse = await chat_user_stream(
                chat_request=chat_request,
                user_context=user_context,
                bot_name='VaHaCha'
            )
        else:
            streaming_resp: StreamingResponse = await chat_stream(
                chat_request=chat_request,
                bot_name='VaHaCha'
            )

        # Đọc từng SSE chunk từ body_iterator
        async for chunk in streaming_resp.body_iterator:
            # Chuẩn hoá text
            text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")

            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue

                # bóc JSON payload
                payload_str = line[len("data:"):].strip()
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    logger.warning(f"Cannot parse JSON: {payload_str}")
                    continue

                # lower không cần thiết ở đây, vì chúng ta chỉ dùng payload["type"] và payload["tokens"]
                evt = payload.get("type")
                tokens = payload.get("tokens", [])
                data_str = "".join(tokens)

                # 1) processing thinking
                if evt in ("header_thinking", "thinking") and not in_response:
                    # append lên thinking_content
                    thinking_content += data_str
                    # edit luôn bot_message (lúc này thinking_content chưa có dòng khởi tạo)
                    await bot_message.edit(content=thinking_content)

                # 2) chuyển sang response
                elif evt == "response":
                    # nếu mới vào lần đầu gặp response, xoá thinking_content
                    if not in_response:
                        in_response = True
                        response_content = data_str
                    else:
                        # đã bắt đầu response, tiếp tục append
                        response_content += data_str

                    # edit bot_message để hiển thị response
                    await bot_message.edit(content=response_content)

                # 3) kết thúc stream
                elif evt == "end":
                    first_chunk, *rest = split_chunks(response_content)
                    await bot_message.edit(content=first_chunk)

                    # 2) gửi các phần tiếp theo dưới dạng tin nhắn mới
                    for chunk in rest:
                        await message.author.send(chunk)

                    # 3) cuối cùng notify hoàn thành
                    await message.author.send("✅ Hoàn thành!")
                    logger.info(f"Finished response for user {message.author.id}")
                    return

        # bảo đảm kết thúc
        await message.author.send("✅ Hoàn thành!")
        logger.info(f"Finished response for user {message.author.id}")
    except Exception as e:
        logger.error(f"Error in process_single_message: {e}", exc_info=True)
        await message.author.send(f"❌ Đã xảy ra lỗi: {e}")


async def fetch_user_context_obj(user_id: int) -> UserContext:
    """Hàm helper để fetch và parse UserContext từ service"""
    import requests

    if user_id==1255008453773099029:
        return UserContext(
            role="seo",
            departments=["mkt 1"],
            teams=["mkt 1"],
            projects=["lofi", "relax"],
            networks=["routenote", "dashgo", "la cupula music"]
        )

    resp = requests.get(f"http://discord-crawl:8200/users/{user_id}")
    if resp.status_code == 200:
        resp_json = {}
        for key, values in resp.json().items():
            if isinstance(values, str):
                resp_json[key] = values.lower()
            if isinstance(values, list):
                resp_json[key] = []
                for value in values:
                    resp_json[key].append(value.lower())
        return UserContext(**resp_json)
    else:
        raise RuntimeError(f"Không fetch được user_context: {resp.status_code}")


@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')
    global workers
    for _ in range(get_core_settings().DISCORD_BOT_NUM_WORKERS):
        worker = asyncio.create_task(process_message_queue())
        workers.append(worker)
    logger.info(f'Started {get_core_settings().DISCORD_BOT_NUM_WORKERS} message queue workers')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    prefix = get_core_settings().DISCORD_BOT_ID
    if message.content.startswith(prefix):
        uid = message.author.id
        now = time.time()
        # reset period
        if now - user_last_message[uid] > get_core_settings().DISCORD_BOT_RATE_LIMIT_PERIOD:
            user_message_count[uid] = 0
        # check limit
        if user_message_count[uid] >= get_core_settings().DISCORD_BOT_MAX_MESSAGES_PER_PERIOD:
            await message.author.send(get_core_settings().DISCORD_BOT_COOLDOWN_MESSAGE)
            return

        user_message_count[uid] += 1
        user_last_message[uid] = now
        prompt = message.content[len(prefix):].strip()
        await message_queue.put((message, prompt))
